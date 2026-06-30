import json
import logging
import sqlite3
from typing import Any

from heiman.database.connector import SQLiteConnector

logger = logging.getLogger(__name__)


class ProductRepo:
    def __init__(self, db: SQLiteConnector):
        self.db = db

    def import_from_sql(self, sql_path: str) -> int:
        count = 0
        try:
            with open(sql_path, 'r', encoding='utf-8') as f:
                content = f.read()

            products = self._parse_sql_products(content)
            for product in products:
                self._upsert_product(product)
                count += 1

            logger.info("[ProductRepo] Imported %d products from %s", count, sql_path)
            return count
        except Exception as e:
            logger.error("[ProductRepo] Failed to import products: %s", e)
            raise

    def _parse_sql_products(self, content: str) -> list[dict]:
        products = []
        import re

        insert_positions = [m.start() for m in re.finditer(r"INSERT INTO", content)]
        logger.debug("[ProductRepo] Found %d INSERT statements", len(insert_positions))

        for pos in insert_positions:
            values_match = re.search(r"VALUES\s*\(", content[pos:pos+500])
            if not values_match:
                continue

            values_start = pos + values_match.end() - 1

            depth = 0
            in_quote = False
            group_start = values_start
            i = values_start

            while i < len(content):
                c = content[i]

                if c == "'" and (i == 0 or content[i-1] != '\\'):
                    in_quote = not in_quote
                elif not in_quote:
                    if c == '(':
                        depth += 1
                    elif c == ')':
                        depth -= 1
                        if depth == 0:
                            value_str = content[group_start+1:i]
                            product = self._parse_value_group(value_str)
                            if product:
                                products.append(product)

                            next_char = content[i+1:i+2]
                            if next_char == ',':
                                i += 2
                                group_start = i
                                continue
                            else:
                                break

                i += 1

        return products

    def _parse_value_group(self, value_str: str) -> dict | None:
        try:
            import csv
            import io
            reader = csv.reader(io.StringIO(value_str), quotechar="'", escapechar='\\', skipinitialspace=True)
            values = next(reader)

            if len(values) < 32:
                return None

            pid = values[0].strip("'")
            if not pid.isdigit() or len(pid) < 15:
                return None

            name = values[1].strip("'")
            classified_name = values[7].strip("'")

            if not name or len(name) < 2:
                return None

            product = {
                'id': pid,
                'name': name,
                'project_id': values[2].strip("'") if values[2] != 'NULL' else None,
                'photo_url': values[3].strip("'") if values[3] != 'NULL' else None,
                'project_name': values[4].strip("'") if values[4] != 'NULL' else None,
                'describe': values[5].strip("'") if values[5] != 'NULL' else None,
                'classified_id': values[6].strip("'"),
                'classified_name': classified_name,
                'message_protocol': values[8].strip("'"),
                'protocol_name': values[9].strip("'"),
                'metadata': values[10].strip("'"),
                'transport_protocol': values[11].strip("'"),
                'network_way': values[12].strip("'"),
                'device_type': values[13].strip("'"),
                'configuration': values[14].strip("'") if values[14] != 'NULL' else None,
                'state': int(values[15]) if values[15] != 'NULL' else 1,
                'creator_id': values[16].strip("'") if values[16] != 'NULL' else None,
                'create_time': int(values[17]) if values[17] != 'NULL' else None,
                'org_id': values[18].strip("'") if values[18] != 'NULL' else None,
                'access_id': values[19].strip("'") if values[19] != 'NULL' else None,
                'access_provider': values[20].strip("'") if values[20] != 'NULL' else None,
                'access_name': values[21].strip("'") if values[21] != 'NULL' else None,
                'store_policy': values[22].strip("'") if values[22] != 'NULL' else None,
                'store_policy_configuration': values[23].strip("'") if values[23] != 'NULL' else None,
                'modifier_id': values[24].strip("'") if values[24] != 'NULL' else None,
                'modify_time': int(values[25]) if values[25] != 'NULL' else None,
                'bind_type': int(values[26]) if values[26] != 'NULL' else 0,
                'network_type': int(values[27]) if values[27] != 'NULL' else 1,
                'target_id': values[28].strip("'") if values[28] != 'NULL' else None,
                'dueros_product': values[29].strip("'") if values[29] != 'NULL' else None,
                'keep_online_second': int(values[30]) if values[30] != 'NULL' else None,
                'ifttt': values[31].strip("'") if values[31] != 'NULL' else None,
            }
            return product
        except Exception as e:
            logger.debug("[ProductRepo] Failed to parse value group: %s", e)
            return None

    def _parse_insert_values(self, values_str: str) -> dict | None:
        return self._parse_value_group(values_str)

    def _upsert_product(self, product: dict) -> None:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO dev_product (
                    id, name, project_id, photo_url, project_name, describe,
                    classified_id, classified_name, message_protocol, protocol_name,
                    metadata, transport_protocol, network_way, device_type,
                    configuration, state, creator_id, create_time, org_id,
                    access_id, access_provider, access_name, store_policy,
                    store_policy_configuration, modifier_id, modify_time,
                    bind_type, network_type, target_id, dueros_product,
                    keep_online_second, ifttt, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    product['id'], product['name'], product['project_id'],
                    product['photo_url'], product['project_name'], product['describe'],
                    product['classified_id'], product['classified_name'],
                    product['message_protocol'], product['protocol_name'],
                    product['metadata'], product['transport_protocol'],
                    product['network_way'], product['device_type'],
                    product['configuration'], product['state'],
                    product['creator_id'], product['create_time'],
                    product['org_id'], product['access_id'],
                    product['access_provider'], product['access_name'],
                    product['store_policy'], product['store_policy_configuration'],
                    product['modifier_id'], product['modify_time'],
                    product['bind_type'], product['network_type'],
                    product['target_id'], product['dueros_product'],
                    product['keep_online_second'], product['ifttt'],
                )
            )

            self._sync_product_properties(conn, product['id'], product.get('metadata'))

            conn.commit()

    def _sync_product_properties(self, conn: sqlite3.Connection, product_id: str, metadata_str: str | None) -> None:
        if not metadata_str:
            return

        try:
            metadata = json.loads(metadata_str)
        except (json.JSONDecodeError, TypeError):
            return

        properties = metadata.get('properties', [])
        if not isinstance(properties, list):
            return

        cursor = conn.cursor()
        cursor.execute("DELETE FROM product_property WHERE product_id = ?", (product_id,))

        for prop in properties:
            if not isinstance(prop, dict):
                continue
            prop_id = prop.get('id', '')
            if not prop_id:
                continue

            value_type = prop.get('valueType', {})
            if isinstance(value_type, dict):
                value_type_str = value_type.get('type', '')
            else:
                value_type_str = ''

            expands = prop.get('expands', {})
            if isinstance(expands, dict):
                expands_str = json.dumps(expands, ensure_ascii=False)
            else:
                expands_str = str(expands) if expands else None

            cursor.execute(
                """
                INSERT INTO product_property (
                    product_id, property_id, property_name, property_type,
                    value_type, expands, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    prop_id,
                    prop.get('name', ''),
                    prop.get('type', ''),
                    value_type_str,
                    expands_str,
                    prop.get('description', ''),
                )
            )

    def get_product(self, product_id: str) -> dict | None:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dev_product WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def list_products(self, classified_name: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if classified_name:
                cursor.execute(
                    "SELECT id, name, classified_name, device_type, photo_url, state FROM dev_product WHERE classified_name = ? ORDER BY name LIMIT ? OFFSET ?",
                    (classified_name, limit, offset)
                )
            else:
                cursor.execute(
                    "SELECT id, name, classified_name, device_type, photo_url, state FROM dev_product ORDER BY name LIMIT ? OFFSET ?",
                    (limit, offset)
                )
            return [dict(row) for row in cursor.fetchall()]

    def list_classifications(self) -> list[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT classified_id, classified_name, COUNT(*) as count FROM dev_product GROUP BY classified_id, classified_name ORDER BY classified_name"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_product_properties(self, product_id: str) -> list[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM product_property WHERE product_id = ? ORDER BY property_id",
                (product_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def search_products(self, keyword: str, limit: int = 50) -> list[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, classified_name, device_type, photo_url, state 
                FROM dev_product 
                WHERE name LIKE ? OR classified_name LIKE ? 
                ORDER BY name LIMIT ?
                """,
                (f'%{keyword}%', f'%{keyword}%', limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_product_count(self) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM dev_product")
            row = cursor.fetchone()
            return row['count'] if row else 0
