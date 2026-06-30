import logging
from enum import Enum
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class ComfortLevel(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class ComfortResult:
    def __init__(
        self,
        level: ComfortLevel,
        score: int,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        co2: Optional[int] = None,
        pm25: Optional[int] = None,
        hcho: Optional[float] = None,
        temperature_status: Optional[str] = None,
        humidity_status: Optional[str] = None,
        co2_status: Optional[str] = None,
        pm25_status: Optional[str] = None,
        hcho_status: Optional[str] = None,
        suggestions: Optional[list] = None,
    ):
        self.level = level
        self.score = score
        self.temperature = temperature
        self.humidity = humidity
        self.co2 = co2
        self.pm25 = pm25
        self.hcho = hcho
        self.temperature_status = temperature_status
        self.humidity_status = humidity_status
        self.co2_status = co2_status
        self.pm25_status = pm25_status
        self.hcho_status = hcho_status
        self.suggestions = suggestions or []

    def to_dict(self):
        return {
            "level": self.level.value,
            "score": self.score,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "co2": self.co2,
            "pm25": self.pm25,
            "hcho": self.hcho,
            "temperature_status": self.temperature_status,
            "humidity_status": self.humidity_status,
            "co2_status": self.co2_status,
            "pm25_status": self.pm25_status,
            "hcho_status": self.hcho_status,
            "suggestions": self.suggestions,
        }


class ComfortEvaluator:
    def __init__(self):
        self.temp_excellent_range = (22, 26)
        self.temp_good_range = (20, 28)
        self.temp_fair_range = (18, 30)
        
        self.humidity_excellent_range = (40, 60)
        self.humidity_good_range = (30, 70)
        self.humidity_fair_range = (20, 80)
        
        self.co2_limits = {
            "excellent": 600,
            "good": 1000,
            "fair": 1500,
            "poor": 2000,
        }
        
        self.pm25_limits = {
            "excellent": 35,
            "good": 75,
            "fair": 150,
            "poor": 350,
        }
        
        self.hcho_limits = {
            "excellent": 0.03,
            "good": 0.08,
            "fair": 0.1,
            "poor": 0.2,
        }

    def evaluate(
        self,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        co2: Optional[int] = None,
        pm25: Optional[int] = None,
        hcho: Optional[float] = None,
    ) -> ComfortResult:
        scores = []
        suggestions = []
        
        temp_status = self._evaluate_temperature(temperature, suggestions)
        if temp_status:
            scores.append(temp_status["score"])
        
        humidity_status = self._evaluate_humidity(humidity, suggestions)
        if humidity_status:
            scores.append(humidity_status["score"])
        
        co2_status = self._evaluate_co2(co2, suggestions)
        if co2_status:
            scores.append(co2_status["score"])
        
        pm25_status = self._evaluate_pm25(pm25, suggestions)
        if pm25_status:
            scores.append(pm25_status["score"])
        
        hcho_status = self._evaluate_hcho(hcho, suggestions)
        if hcho_status:
            scores.append(hcho_status["score"])
        
        if not scores:
            return ComfortResult(level=ComfortLevel.FAIR, score=50, suggestions=["暂无足够数据评估舒适度"])
        
        avg_score = sum(scores) / len(scores)
        level = self._score_to_level(avg_score)
        
        return ComfortResult(
            level=level,
            score=round(avg_score),
            temperature=temperature,
            humidity=humidity,
            co2=co2,
            pm25=pm25,
            hcho=hcho,
            temperature_status=temp_status["status"] if temp_status else None,
            humidity_status=humidity_status["status"] if humidity_status else None,
            co2_status=co2_status["status"] if co2_status else None,
            pm25_status=pm25_status["status"] if pm25_status else None,
            hcho_status=hcho_status["status"] if hcho_status else None,
            suggestions=suggestions,
        )

    def _evaluate_temperature(self, temp: Optional[float], suggestions: list) -> Optional[Dict]:
        if temp is None:
            return None
        
        if self.temp_excellent_range[0] <= temp <= self.temp_excellent_range[1]:
            return {"score": 100, "status": "极佳"}
        
        if self.temp_good_range[0] <= temp <= self.temp_good_range[1]:
            diff = abs(temp - 24)
            score = max(70, 100 - diff * 5)
            return {"score": score, "status": "良好"}
        
        if self.temp_fair_range[0] <= temp <= self.temp_fair_range[1]:
            diff = abs(temp - 24)
            score = max(40, 70 - diff * 3)
            if temp < 20:
                suggestions.append(f"温度较低 ({temp}°C)，建议开启暖气或增加衣物")
            elif temp > 28:
                suggestions.append(f"温度较高 ({temp}°C)，建议开启空调或通风")
            return {"score": score, "status": "一般"}
        
        score = 20
        if temp < 18:
            suggestions.append(f"温度过低 ({temp}°C)，请立即采取保暖措施")
        else:
            suggestions.append(f"温度过高 ({temp}°C)，请立即降温")
        return {"score": score, "status": "较差"}

    def _evaluate_humidity(self, humidity: Optional[float], suggestions: list) -> Optional[Dict]:
        if humidity is None:
            return None
        
        if self.humidity_excellent_range[0] <= humidity <= self.humidity_excellent_range[1]:
            return {"score": 100, "status": "极佳"}
        
        if self.humidity_good_range[0] <= humidity <= self.humidity_good_range[1]:
            diff = abs(humidity - 50)
            score = max(70, 100 - diff * 1.5)
            return {"score": score, "status": "良好"}
        
        if self.humidity_fair_range[0] <= humidity <= self.humidity_fair_range[1]:
            diff = abs(humidity - 50)
            score = max(40, 70 - diff)
            if humidity < 30:
                suggestions.append(f"空气干燥 ({humidity}%RH)，建议使用加湿器")
            elif humidity > 70:
                suggestions.append(f"空气潮湿 ({humidity}%RH)，建议开启除湿或通风")
            return {"score": score, "status": "一般"}
        
        score = 20
        if humidity < 20:
            suggestions.append(f"空气极干 ({humidity}%RH)，请立即使用加湿器")
        else:
            suggestions.append(f"空气极湿 ({humidity}%RH)，请立即除湿")
        return {"score": score, "status": "较差"}

    def _evaluate_co2(self, co2: Optional[int], suggestions: list) -> Optional[Dict]:
        if co2 is None:
            return None
        
        if co2 <= self.co2_limits["excellent"]:
            return {"score": 100, "status": "极佳"}
        
        if co2 <= self.co2_limits["good"]:
            score = max(70, 100 - (co2 - 600) * 0.075)
            return {"score": score, "status": "良好"}
        
        if co2 <= self.co2_limits["fair"]:
            score = max(40, 70 - (co2 - 1000) * 0.06)
            suggestions.append(f"CO2浓度较高 ({co2} ppm)，建议开窗通风")
            return {"score": score, "status": "一般"}
        
        if co2 <= self.co2_limits["poor"]:
            score = max(20, 40 - (co2 - 1500) * 0.04)
            suggestions.append(f"CO2浓度过高 ({co2} ppm)，请立即开窗通风")
            return {"score": score, "status": "较差"}
        
        score = 10
        suggestions.append(f"CO2浓度危险 ({co2} ppm)，请立即离开并通风")
        return {"score": score, "status": "危险"}

    def _evaluate_pm25(self, pm25: Optional[int], suggestions: list) -> Optional[Dict]:
        if pm25 is None:
            return None
        
        if pm25 <= self.pm25_limits["excellent"]:
            return {"score": 100, "status": "极佳"}
        
        if pm25 <= self.pm25_limits["good"]:
            score = max(70, 100 - (pm25 - 35) * 0.8)
            return {"score": score, "status": "良好"}
        
        if pm25 <= self.pm25_limits["fair"]:
            score = max(40, 70 - (pm25 - 75) * 0.4)
            suggestions.append(f"PM2.5偏高 ({pm25} μg/m³)，建议关闭门窗并使用空气净化器")
            return {"score": score, "status": "一般"}
        
        if pm25 <= self.pm25_limits["poor"]:
            score = max(20, 40 - (pm25 - 150) * 0.1)
            suggestions.append(f"PM2.5严重超标 ({pm25} μg/m³)，请避免外出")
            return {"score": score, "status": "较差"}
        
        score = 10
        suggestions.append(f"PM2.5极度危险 ({pm25} μg/m³)，请佩戴口罩")
        return {"score": score, "status": "危险"}

    def _evaluate_hcho(self, hcho: Optional[float], suggestions: list) -> Optional[Dict]:
        if hcho is None:
            return None
        
        if hcho <= self.hcho_limits["excellent"]:
            return {"score": 100, "status": "极佳"}
        
        if hcho <= self.hcho_limits["good"]:
            score = max(70, 100 - (hcho - 0.03) * 600)
            return {"score": score, "status": "良好"}
        
        if hcho <= self.hcho_limits["fair"]:
            score = max(40, 70 - (hcho - 0.08) * 750)
            suggestions.append(f"甲醛超标 ({hcho} mg/m³)，建议加强通风")
            return {"score": score, "status": "一般"}
        
        if hcho <= self.hcho_limits["poor"]:
            score = max(20, 40 - (hcho - 0.1) * 200)
            suggestions.append(f"甲醛严重超标 ({hcho} mg/m³)，请立即通风")
            return {"score": score, "status": "较差"}
        
        score = 10
        suggestions.append(f"甲醛极度危险 ({hcho} mg/m³)，请远离")
        return {"score": score, "status": "危险"}

    def _score_to_level(self, score: float) -> ComfortLevel:
        if score >= 85:
            return ComfortLevel.EXCELLENT
        elif score >= 70:
            return ComfortLevel.GOOD
        elif score >= 40:
            return ComfortLevel.FAIR
        else:
            return ComfortLevel.POOR

    def evaluate_device(self, device_data: Dict) -> ComfortResult:
        return self.evaluate(
            temperature=device_data.get("temperature"),
            humidity=device_data.get("humidity"),
            co2=device_data.get("co2"),
            pm25=device_data.get("pm25"),
            hcho=device_data.get("hcho"),
        )
