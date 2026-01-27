
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import (
    QueryRequest, DropTableRequest, DropNamespaceRequest, 
    OperationType, Filter
)

class TestFixes(unittest.TestCase):
    
    @patch('src.operations_full_iceberg.get_config')
    @patch('src.operations_full_iceberg.FullIcebergOperations._init_pyiceberg_catalog')
    @patch('src.operations_full_iceberg.FullIcebergOperations._init_duckdb')
    def setUp(self, mock_duckdb, mock_catalog, mock_config):
        # Setup mocks
        mock_config.return_value = MagicMock()
        self.mock_conn = MagicMock()
        mock_duckdb.return_value = self.mock_conn
        self.mock_catalog = MagicMock()
        mock_catalog.return_value = self.mock_catalog
        
        from src.operations_full_iceberg import FullIcebergOperations
        # Force re-init
        import src.operations_full_iceberg
        src.operations_full_iceberg._iceberg_ops = None
        
        self.ops = FullIcebergOperations()
        
        # Mock _get_metadata_path to return a dummy path
        self.ops._get_metadata_path = MagicMock(return_value="s3://bucket/path/metadata.json")

    def test_query_generates_correct_cte_sql(self):
        """Verify that QUERY operation generates SQL with CTE and ROW_NUMBER"""
        req = QueryRequest(
            tenant_id="test_tenant",
            table="users",
            filters=[Filter(field="status", operator="eq", value="active")]
        )
        
        # Mock fetchdf to return empty (we just want to check the SQL)
        mock_df = MagicMock()
        mock_df.to_dict.return_value = []
        mock_df.empty = True
        self.mock_conn.execute.return_value.fetchdf.return_value = mock_df
        
        self.ops.query(req)
        
        # Get the SQL passed to execute
        call_args = self.mock_conn.execute.call_args
        sql_executed = call_args[0][0]
        
        print("\nGenerated SQL:")
        print(sql_executed)
        
        # Assertions
        self.assertIn("WITH ranked_records AS", sql_executed)
        self.assertIn("ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC) as rn", sql_executed)
        self.assertIn("WHERE rn = 1", sql_executed)
        self.assertIn("AND _deleted IS NOT TRUE", sql_executed)
        # Verify user filter is present (it might be in params or SQL depending on builder)
        # In our implementation, we add user filters to the outer query
        
    def test_drop_table_calls_catalog(self):
        """Verify DROP_TABLE calls catalog.drop_table"""
        req = DropTableRequest(
            tenant_id="test_tenant",
            table="users",
            purge=True
        )
        
        self.ops.drop_table(req)
        
        self.mock_catalog.drop_table.assert_called_once()
        args, kwargs = self.mock_catalog.drop_table.call_args
        self.assertIn("test_tenant_default.users", args[0])
        self.assertTrue(kwargs['purge'])

    def test_drop_namespace_calls_catalog(self):
        """Verify DROP_NAMESPACE calls catalog.drop_namespace"""
        req = DropNamespaceRequest(
            tenant_id="test_tenant",
            namespace="analytics"
        )
        
        self.ops.drop_namespace(req)
        
        self.mock_catalog.drop_namespace.assert_called_once_with("test_tenant_analytics")

if __name__ == '__main__':
    unittest.main()
