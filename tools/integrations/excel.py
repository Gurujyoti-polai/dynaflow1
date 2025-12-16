import os
from typing import Dict, Any, List
from openpyxl import Workbook


class ExcelTool:
    name = "excel"
    description = "Create and write Excel spreadsheets"
    category = "productivity"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "description": self.description,
            "actions": {
                "create_spreadsheet": {
                    "description": "Create an Excel (.xlsx) file from structured data",
                    "parameters": {
                        "filename": {
                            "type": "string",
                            "required": True,
                            "description": "Excel file name (e.g. report.xlsx)"
                        },
                        "data": {
                            "type": "array",
                            "required": True,
                            "description": "List of objects. Keys become columns",
                            "items": {
                                "type": "object"
                            }
                        }
                    }
                }
            }
        }

    def execute(self, action: str, parameters: Dict[str, Any], mode="real") -> Dict[str, Any]:
        if action != "create_spreadsheet":
            return {"error": f"Unknown action: {action}"}

        filename = parameters.get("filename")
        data: List[Dict[str, Any]] = parameters.get("data", [])

        if not filename or not data:
            return {"error": "filename and data are required"}

        output_dir = os.getenv("EXCEL_OUTPUT_DIR", "./output")
        os.makedirs(output_dir, exist_ok=True)

        filepath = os.path.join(output_dir, filename)

        wb = Workbook()
        ws = wb.active

        # Headers
        headers = list(data[0].keys())
        ws.append(headers)

        # Rows
        for row in data:
            ws.append([row.get(h, "") for h in headers])

        wb.save(filepath)

        return {
            "status": 200,
            "filepath": filepath,
            "message": "Excel file created successfully"
        }
