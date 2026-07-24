import logging
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EnergySource(str, Enum):
    GRID = "grid"
    SOLAR = "solar"
    BATTERY = "battery"
    GENERATOR = "generator"


class EnergyConsumer(str, Enum):
    LIGHTING = "lighting"
    HEATING = "heating"
    COOLING = "cooling"
    APPLIANCES = "appliances"
    EV_CHARGER = "ev_charger"
    OTHER = "other"


class EnergyMode(str, Enum):
    ECONOMY = "economy"
    COMFORT = "comfort"
    AUTO = "auto"
    OFF = "off"


@dataclass
class EnergyReading:
    timestamp: float
    source: EnergySource
    consumer: EnergyConsumer
    power_watts: float
    energy_kwh: float = 0.0
    price_per_kwh: float = 0.0


@dataclass
class EnergyStats:
    total_consumed_kwh: float = 0.0
    total_generated_kwh: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    battery_charge_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    estimated_cost: float = 0.0


@dataclass
class PeakPeriod:
    start_hour: int
    end_hour: int
    is_peak: bool = True
    price_multiplier: float = 1.5


class EnergyManager:
    def __init__(self):
        self._readings: List[EnergyReading] = []
        self._stats_cache: Dict[str, EnergyStats] = {}
        self._peak_periods: List[PeakPeriod] = []
        self._energy_mode = EnergyMode.AUTO
        self._battery_capacity_kwh = 0.0
        self._battery_soc = 0.0
        self._price_per_kwh = 0.0
        self._initialized = False

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        
        self._battery_capacity_kwh = config.get("battery_capacity_kwh", 10.0)
        self._battery_soc = config.get("initial_soc", 50.0)
        self._price_per_kwh = config.get("price_per_kwh", 0.8)
        self._energy_mode = EnergyMode(config.get("energy_mode", "auto"))
        
        self._load_peak_periods(config.get("peak_periods", []))
        asyncio.create_task(self._periodic_stats_update())
        self._initialized = True
        logger.info("Energy manager initialized")

    def _load_peak_periods(self, periods_config: List[Dict[str, Any]]):
        if periods_config:
            for period in periods_config:
                self._peak_periods.append(PeakPeriod(
                    start_hour=period.get("start_hour", 8),
                    end_hour=period.get("end_hour", 22),
                    is_peak=period.get("is_peak", True),
                    price_multiplier=period.get("price_multiplier", 1.5),
                ))
        else:
            self._peak_periods = [
                PeakPeriod(start_hour=8, end_hour=12, price_multiplier=1.5),
                PeakPeriod(start_hour=18, end_hour=22, price_multiplier=1.5),
            ]

    async def record_reading(self, reading: EnergyReading):
        self._readings.append(reading)
        
        if len(self._readings) > 10000:
            self._readings = self._readings[-10000:]
        
        await self._update_stats()

    async def get_current_power(self) -> Dict[str, float]:
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        
        recent_readings = [
            r for r in self._readings
            if r.timestamp >= last_hour.timestamp()
        ]
        
        if not recent_readings:
            return {
                "total_power_watts": 0.0,
                "solar_power_watts": 0.0,
                "grid_power_watts": 0.0,
                "net_power_watts": 0.0,
            }
        
        total_power = sum(r.power_watts for r in recent_readings if r.source != EnergySource.SOLAR)
        solar_power = sum(r.power_watts for r in recent_readings if r.source == EnergySource.SOLAR)
        
        return {
            "total_power_watts": total_power,
            "solar_power_watts": solar_power,
            "grid_power_watts": max(0, total_power - solar_power),
            "net_power_watts": solar_power - total_power,
        }

    async def get_daily_stats(self, date: Optional[datetime] = None, days: int = 1) -> List[Dict]:
        # Try to get real device data from database
        real_stats = await self._get_real_device_stats(days)
        if real_stats:
            return real_stats

        if days > 1:
            result = []
            for i in range(days):
                target_date = datetime.now() - timedelta(days=i)
                date_str = target_date.strftime("%Y-%m-%d")
                
                if date_str in self._stats_cache:
                    stats = self._stats_cache[date_str]
                else:
                    start_ts = target_date.replace(hour=0, minute=0, second=0).timestamp()
                    end_ts = target_date.replace(hour=23, minute=59, second=59).timestamp()
                    
                    day_readings = [
                        r for r in self._readings
                        if start_ts <= r.timestamp <= end_ts
                    ]
                    
                    stats = self._calculate_stats(day_readings)
                    self._stats_cache[date_str] = stats
                
                result.append({
                    "date": date_str,
                    "consumption_kwh": round(stats.total_consumed_kwh, 2),
                    "generation_kwh": round(stats.total_generated_kwh, 2),
                    "peak_watts": 0,
                    "avg_watts": 0,
                })
            return result
        
        target_date = date or datetime.now()
        date_str = target_date.strftime("%Y-%m-%d")
        
        if date_str in self._stats_cache:
            stats = self._stats_cache[date_str]
        else:
            start_ts = target_date.replace(hour=0, minute=0, second=0).timestamp()
            end_ts = target_date.replace(hour=23, minute=59, second=59).timestamp()
            
            day_readings = [
                r for r in self._readings
                if start_ts <= r.timestamp <= end_ts
            ]
            
            stats = self._calculate_stats(day_readings)
            self._stats_cache[date_str] = stats
        
        return [{
            "date": date_str,
            "consumption_kwh": round(stats.total_consumed_kwh, 2),
            "generation_kwh": round(stats.total_generated_kwh, 2),
            "peak_watts": 0,
            "avg_watts": 0,
        }]

    async def _get_real_device_stats(self, days: int) -> List[Dict]:
        """Get energy estimates based on real device data from database."""
        try:
            from heiman.database.connector import get_db_connector

            db = get_db_connector()
            result = []

            # Device type power estimates (watts)
            device_power = {
                "gateway": 2.0,
                "temperature": 0.5,
                "smoke": 0.3,
                "contact": 0.1,
                "plug": 5.0,
                "motion": 0.2,
                "humidity": 0.5,
                "co2": 1.0,
                "pm25": 1.0,
                "water_leak": 0.1,
                "gas": 0.3,
                "lock": 2.0,
                "switch": 1.0,
                "light": 10.0,
                "fan": 15.0,
                "ac": 800.0,
                "heater": 1000.0,
                "tv": 100.0,
                "fridge": 150.0,
            }

            for i in range(days):
                target_date = datetime.now() - timedelta(days=i)
                date_str = target_date.strftime("%Y-%m-%d")

                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    # Get device count by type for this day
                    cursor.execute("""
                        SELECT sensor_type, COUNT(DISTINCT did) as device_count
                        FROM sensor_logs
                        WHERE date(timestamp) = date(?)
                        GROUP BY sensor_type
                    """, (date_str,))
                    rows = cursor.fetchall()

                    if not rows:
                        # No data for this day, try latest device counts
                        cursor.execute("""
                            SELECT sensor_type, COUNT(DISTINCT did) as device_count
                            FROM sensor_logs
                            GROUP BY sensor_type
                        """)
                        rows = cursor.fetchall()

                    if not rows:
                        continue

                    total_power_watts = 0.0
                    for row in rows:
                        sensor_type = row["sensor_type"]
                        count = row["device_count"]
                        power = device_power.get(sensor_type, 1.0) * count
                        total_power_watts += power

                    # Estimate daily consumption: power (watts) * 24 hours / 1000 = kWh
                    daily_kwh = round(total_power_watts * 24 / 1000, 2)

                    result.append({
                        "date": date_str,
                        "consumption_kwh": daily_kwh,
                        "generation_kwh": 0.0,
                        "peak_watts": int(total_power_watts),
                        "avg_watts": int(total_power_watts),
                    })

            return result if result else []
        except Exception as e:
            logger.warning("Failed to get real device stats: %s", e)
            return []

    def _calculate_stats(self, readings: List[EnergyReading]) -> EnergyStats:
        stats = EnergyStats()
        
        for reading in readings:
            if reading.source == EnergySource.SOLAR:
                stats.total_generated_kwh += reading.energy_kwh
            else:
                stats.total_consumed_kwh += reading.energy_kwh
        
        stats.grid_import_kwh = max(0, stats.total_consumed_kwh - stats.total_generated_kwh)
        stats.grid_export_kwh = max(0, stats.total_generated_kwh - stats.total_consumed_kwh)
        stats.estimated_cost = stats.grid_import_kwh * self._price_per_kwh
        
        return stats

    async def _update_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        start_ts = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        day_readings = [r for r in self._readings if r.timestamp >= start_ts]
        stats = self._calculate_stats(day_readings)
        self._stats_cache[today] = stats

    async def _periodic_stats_update(self):
        while True:
            await self._update_stats()
            await asyncio.sleep(60)

    def is_peak_hour(self) -> bool:
        hour = datetime.now().hour
        for period in self._peak_periods:
            if period.is_peak and period.start_hour <= hour < period.end_hour:
                return True
        return False

    def get_current_price(self) -> float:
        if self.is_peak_hour():
            for period in self._peak_periods:
                if period.start_hour <= datetime.now().hour < period.end_hour:
                    return self._price_per_kwh * period.price_multiplier
        return self._price_per_kwh

    async def optimize_consumption(self) -> Dict[str, Any]:
        power = await self.get_current_power()
        is_peak = self.is_peak_hour()
        current_price = self.get_current_price()
        
        recommendations = []
        
        if is_peak and power["grid_power_watts"] > 1000:
            recommendations.append({
                "action": "reduce_non_essential_load",
                "description": "当前处于用电高峰，建议关闭非必要电器",
                "priority": "high",
                "estimated_savings_watts": 500,
            })
        
        if self._battery_soc > 80 and not is_peak:
            recommendations.append({
                "action": "charge_battery",
                "description": "电价较低，建议利用电网为电池充电",
                "priority": "medium",
            })
        
        if self._battery_soc < 20 and is_peak:
            recommendations.append({
                "action": "use_battery",
                "description": "电池电量较低，建议切换到电池供电",
                "priority": "high",
            })
        
        if power["solar_power_watts"] > 1000 and self._battery_soc < 90:
            recommendations.append({
                "action": "use_solar",
                "description": "太阳能发电充足，建议优先使用太阳能",
                "priority": "low",
            })
        
        return {
            "current_power": power,
            "is_peak_hour": is_peak,
            "current_price_per_kwh": round(current_price, 2),
            "battery_soc": self._battery_soc,
            "recommendations": recommendations,
        }

    async def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        start_date = datetime(year, month, 1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        start_ts = start_date.timestamp()
        end_ts = end_date.timestamp()
        
        month_readings = [
            r for r in self._readings
            if start_ts <= r.timestamp <= end_ts
        ]
        
        stats = self._calculate_stats(month_readings)
        
        return {
            "year": year,
            "month": month,
            "total_consumed_kwh": round(stats.total_consumed_kwh, 2),
            "total_generated_kwh": round(stats.total_generated_kwh, 2),
            "grid_import_kwh": round(stats.grid_import_kwh, 2),
            "grid_export_kwh": round(stats.grid_export_kwh, 2),
            "estimated_cost": round(stats.estimated_cost, 2),
            "average_daily_consumption": round(stats.total_consumed_kwh / (end_date.day + 1), 2),
        }

    async def set_energy_mode(self, mode: EnergyMode):
        self._energy_mode = mode
        logger.info(f"Energy mode changed to {mode.value}")

    async def update_battery_soc(self, soc: float):
        self._battery_soc = max(0, min(100, soc))
        logger.debug(f"Battery SOC updated to {self._battery_soc}%")

    async def get_energy_report(self, days: int = 7) -> Dict[str, Any]:
        reports = []
        total_consumed = 0.0
        total_generated = 0.0

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            stats_list = await self.get_daily_stats(date, days=1)

            if stats_list and len(stats_list) > 0:
                stats = stats_list[0]
                consumed = stats.get("consumption_kwh", 0)
                generated = stats.get("generation_kwh", 0)
            else:
                consumed = 0.0
                generated = 0.0

            total_consumed += consumed
            total_generated += generated

            reports.append({
                "date": date_str,
                "consumption_kwh": round(consumed, 2),
                "generation_kwh": round(generated, 2),
            })

        avg_daily = total_consumed / days if days > 0 else 0.0

        return {
            "period_days": days,
            "total_consumption_kwh": round(total_consumed, 2),
            "total_generation_kwh": round(total_generated, 2),
            "average_daily_consumption_kwh": round(avg_daily, 2),
            "peak_consumption_watts": 0,
            "energy_savings_pct": 0.0,
            "recommendations": [],
            "daily_reports": reports,
        }