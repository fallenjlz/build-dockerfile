import csv
from google.cloud import bigquery
from google.api_core.exceptions import BadRequest
import sys
import os
from datetime import datetime, timedelta

class BigQueryManager:
    def __init__(self):
        self.csv_file = os.getenv('CSV_FILE')
        self.ddl_dir = os.getenv('DDL_DIRECTORY')
        self.timestamp_file = 'timestamp.txt'
        self.view_backup_dir = os.getenv('VIEW_BACKUP_DIRECTORY', '.')
        self.procedure_backup_dir = os.getenv('PROCEDURE_BACKUP_DIRECTORY', '.')

        if not self.csv_file or not self.ddl_dir:
            raise ValueError("CSV_FILE and DDL_DIRECTORY environment variables must be set.")

        os.makedirs(self.view_backup_dir, exist_ok=True)
        os.makedirs(self.procedure_backup_dir, exist_ok=True)

        self.client = bigquery.Client()
        self.tables = self.load_config(self.csv_file)
        self.error_found = False
        self.timestamp_ms = self.load_timestamp()

    def load_config(self, csv_file):
        tables = []
        with open(csv_file, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                tables.append({
                    'project': row['project'],
                    'dataset': row['dataset'],
                    'table': row['table'],
                    'verify_query': row.get('verify_query', None),
                    'is_new': row['is_new'].lower() == 'true',
                    'is_view': row['is_view'].lower() == 'true',
                    'is_procedure': row.get('is_procedure', 'false').lower() == 'true'
                })
        return tables

    def load_timestamp(self):
        if os.path.exists(self.timestamp_file):
            with open(self.timestamp_file, 'r') as file:
                return int(file.read().strip())
        return None

    def save_timestamp(self, timestamp_ms):
        with open(self.timestamp_file, 'w') as file:
            file.write(str(timestamp_ms))
        print(f"Timestamp {timestamp_ms} ms saved to {self.timestamp_file}")

    def get_bigquery_current_time_in_ms(self):
        query = "SELECT UNIX_MICROS(CURRENT_TIMESTAMP()) AS current_time_ms"
        try:
            query_job = self.client.query(query)
            results = query_job.result()
            for row in results:
                bigquery_timestamp_ms = row["current_time_ms"] // 1000
                adjusted_timestamp_ms = bigquery_timestamp_ms - 60000
                print(f"Timestamp from BigQuery adjusted by 1 minute: {adjusted_timestamp_ms} ms")
                return adjusted_timestamp_ms
        except Exception as e:
            print(f"Error getting current timestamp from BigQuery: {e}")
            return None

    def record_timestamp(self):
        self.timestamp_ms = self.get_bigquery_current_time_in_ms()
        if self.timestamp_ms:
            self.save_timestamp(self.timestamp_ms)

    def backup_view_or_procedure(self, dataset, name, is_view):
        object_type = 'VIEW' if is_view else 'PROCEDURE'
        backup_dir = self.view_backup_dir if is_view else self.procedure_backup_dir
        backup_file = os.path.join(backup_dir, f"{dataset}_{name}.sql")

        query = f"SHOW CREATE {object_type} `{self.tables[0]['project']}.{dataset}.{name}`"
        print(f"Backing up {object_type}: {self.tables[0]['project']}.{dataset}.{name}")
        try:
            query_job = self.client.query(query)
            result = query_job.result()
            for row in result:
                definition = row['ddl']
                with open(backup_file, 'w') as file:
                    file.write(definition)
                print(f"{object_type} definition backed up to {backup_file}")
        except Exception as e:
            print(f"Error backing up {object_type}: {e}")
            self.error_found = True

    def restore_view_or_procedure(self, dataset, name, is_view):
        object_type = 'VIEW' if is_view else 'PROCEDURE'
        backup_dir = self.view_backup_dir if is_view else self.procedure_backup_dir
        backup_file = os.path.join(backup_dir, f"{dataset}_{name}.sql")

        if not os.path.exists(backup_file):
            print(f"Backup for {object_type} not found. Skipping.")
            return

        print(f"Restoring {object_type} from backup: {backup_file}")
        with open(backup_file, 'r') as file:
            definition = file.read()

        try:
            self.client.query(definition).result()
            print(f"Restored {object_type} {name} from backup.")
        except BadRequest as e:
            print(f"Error restoring {object_type}: {e}")
            self.error_found = True

    def delete_table_or_view_or_procedure(self, dataset, name, is_view, is_procedure):
        if is_procedure:
            object_type = "PROCEDURE"
        elif is_view:
            object_type = "VIEW"
        else:
            object_type = "TABLE"

        target_id = f"{self.tables[0]['project']}.{dataset}.{name}"
        print(f"Deleting newly created {object_type}: {target_id}")

        delete_query = f"DROP {object_type} `{target_id}`"
        try:
            self.client.query(delete_query).result()
            print(f"Deleted {object_type}: {target_id}")
        except BadRequest as e:
            print(f"Error deleting {object_type}: {e}")
            self.error_found = True

    def rollback_all_tables(self):
        print("Rolling back all tables, views, and procedures...")

        for table in self.tables:
            dataset = table['dataset']
            name = table['table']
            is_new = table['is_new']
            is_view = table['is_view']
            is_procedure = table['is_procedure']

            if is_new:
                # Delete newly created tables, views, or procedures
                self.delete_table_or_view_or_procedure(dataset, name, is_view, is_procedure)
            else:
                if is_view:
                    self.restore_view_or_procedure(dataset, name, True)
                elif is_procedure:
                    self.restore_view_or_procedure(dataset, name, False)
                else:
                    self.restore_table(dataset, name)

    def restore_table(self, dataset, table):
        target_table_id = f"{self.tables[0]['project']}.{dataset}.{table}"
        if not self.timestamp_ms:
            print("No timestamp recorded. Fetching a new timestamp...")
            self.record_timestamp()

        if not self.timestamp_ms:
            print(f"Failed to fetch timestamp. Skipping restore for {target_table_id}.")
            return

        print(f"Restoring {target_table_id} to timestamp: {self.timestamp_ms}")
        restore_query = f"""
        CREATE OR REPLACE TABLE `{target_table_id}` AS 
        SELECT * FROM `{target_table_id}` 
        FOR SYSTEM TIME AS OF TIMESTAMP_MICROS({self.timestamp_ms} * 1000)
        """
        try:
            self.client.query(restore_query).result()
            print(f"Restored table: {target_table_id}")
        except BadRequest as e:
            print(f"Error restoring table: {e}")
            self.error_found = True

    def backup_and_execute_ddls(self):
        print("Executing DDLs from directory...")
        self.record_timestamp()

        for table in self.tables:
            if table['is_view']:
                self.backup_view_or_procedure(table['dataset'], table['table'], True)
            elif table['is_procedure']:
                self.backup_view_or_procedure(table['dataset'], table['table'], False)

            ddl_file = f"{table['dataset']}_{table['table']}.sql"
            ddl_path = os.path.join(self.ddl_dir, ddl_file)
            with open(ddl_path, 'r') as file:
                ddl_statement = file.read()
                print(f"Executing DDL: {ddl_file}")
                try:
                    self.client.query(ddl_statement).result()
                    print(f"DDL executed successfully: {ddl_file}")
                except BadRequest as e:
                    print(f"Error executing DDL: {e}")
                    self.rollback_all_tables()
                    self.error_found = True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backup_and_rollback.py <action>")
    else:
        action = sys.argv[1]
        manager = BigQueryManager()

        if action == 'execute':
            manager.backup_and_execute_ddls()
        elif action == 'rollback':
            manager.rollback_all_tables()
        else:
            print("Invalid action. Use 'execute' or 'rollback'.")

        if manager.error_found:
            sys.exit(1)
        else:
            sys.exit(0)