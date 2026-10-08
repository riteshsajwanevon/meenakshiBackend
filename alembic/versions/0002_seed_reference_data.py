"""Seed reference data: roles, departments, settings and the five report templates.

Equivalent of the Java backend's V2__seed.sql. Template columns come from
ProjectCode/templates.json (the annotated sample forms).

NOTE: field regions are evenly spaced placeholders across the table area. Port the
calibrated values from the Java backend's V3__calibrate_regions.sql in a later migration.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = [
    ("ADMIN", "Administrator"),
    ("QUALITY_INSPECTOR", "Quality Inspector"),
    ("OPERATOR", "Operator"),
    ("VIEWER", "Viewer"),
]

DEPARTMENTS = [
    ("INCOMING_QA", "Incoming QA"),
    ("PRESS_SHOP", "Press Shop"),
    ("WELD_SHOP", "Weld Shop"),
    ("PLATING", "Plating"),
    ("POWDER_COATING", "Powder Coating"),
    ("STORES", "Stores"),
]

SETTINGS = [
    ("ocr.verified-threshold", "0.85", "Fields read with at least this confidence are marked VERIFIED"),
    ("ocr.review-threshold", "0.60", "Fields read with at least this confidence are marked NEEDS_REVIEW (below: ERROR)"),
    ("upload.max-bytes", "10485760", "Maximum upload size in bytes"),
]

# The month header field, at the top-right of every form.
MONTH_FIELD = ("month", "Month", "MONTH", True)
MONTH_REGION = (0.62, 0.055, 0.28, 0.04)

# (field_key, label, data_type, required) for each table column, left to right.
_SUPPLIER_REPORT_START = [
    ("date", "Date", "DATE", True),
    ("partName", "Part Name", "TEXT", True),
    ("supplierName", "Supplier Name", "TEXT", True),
    ("lotQty", "Lot Qty", "NUMBER", True),
]
_SUPPLIER_REPORT_END = [
    ("okQty", "OK Qty", "NUMBER", False),
    ("problemDescription", "Problem Description", "TEXT", True),
    ("remarks", "Remarks", "TEXT", False),
]

TEMPLATES = [
    {
        "code": "SUPPLIER_REJECTION",
        "name": "Supplier Rejection Report",
        "description": "Incoming material rejected at receipt, per supplier and part.",
        "quantity_field_key": "rejectionQty",
        "columns": [*_SUPPLIER_REPORT_START, ("rejectionQty", "Rejection Qty", "NUMBER", True), *_SUPPLIER_REPORT_END],
    },
    {
        "code": "SUPPLIER_REWORK",
        "name": "Supplier Rework Report",
        "description": "Incoming material sent for rework, per supplier and part.",
        "quantity_field_key": "reworkQty",
        "columns": [*_SUPPLIER_REPORT_START, ("reworkQty", "Rework Qty", "NUMBER", True), *_SUPPLIER_REPORT_END],
    },
    {
        "code": "SUPPLIER_SEGREGATION",
        "name": "Supplier Segregation Report",
        "description": "Incoming lots that needed segregation, per supplier and part.",
        "quantity_field_key": "segregationQty",
        "columns": [*_SUPPLIER_REPORT_START, ("segregationQty", "Segregation Qty", "NUMBER", True), *_SUPPLIER_REPORT_END],
    },
    {
        "code": "SUPPLIER_LOT_REJECTION_SUMMARY",
        "name": "Supplier Lot Rejection Summary",
        "description": "Monthly summary of lot rework/rejection with actions and CAPA status.",
        "quantity_field_key": "rejQty",
        "columns": [
            *_SUPPLIER_REPORT_START,
            ("rewQty", "Rework Qty", "NUMBER", False),
            ("rejQty", "Rejection Qty", "NUMBER", True),
            ("okQty", "OK Qty", "NUMBER", False),
            ("problemDescription", "Problem Description", "TEXT", True),
            ("action", "Action", "TEXT", False),
            ("returnStatus", "Return Status", "TEXT", False),
            ("capaStatus", "CAPA Status", "TEXT", False),
            ("remarks", "Remarks", "TEXT", False),
        ],
    },
    {
        "code": "SCRAP_NOTE",
        "name": "Scrap Note",
        "description": "Items scrapped, with vendor and reason.",
        "quantity_field_key": "rejectionQty",
        "columns": [
            ("sNo", "S.No", "NUMBER", False),
            ("itemCode", "Item Code", "TEXT", False),
            ("itemName", "Item Name", "TEXT", True),
            ("unit", "Unit", "TEXT", False),
            ("rejectionQty", "Rejection Qty", "NUMBER", True),
            ("vendorName", "Vendor Name", "TEXT", True),
            ("reasonRemarks", "Reason / Remarks", "TEXT", True),
        ],
    },
]

# Table area on the page (fractions of page width/height) used for placeholder column regions.
TABLE_LEFT, TABLE_RIGHT, TABLE_TOP, TABLE_HEIGHT = 0.03, 0.97, 0.17, 0.65

roles_table = sa.table("roles", sa.column("code", sa.String), sa.column("name", sa.String))
departments_table = sa.table("departments", sa.column("code", sa.String), sa.column("name", sa.String))
settings_table = sa.table(
    "app_settings", sa.column("key", sa.String), sa.column("value", sa.Text), sa.column("description", sa.Text)
)
templates_table = sa.table(
    "report_templates",
    sa.column("id", sa.BigInteger),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.Text),
    sa.column("quantity_field_key", sa.String),
)
fields_table = sa.table(
    "template_fields",
    sa.column("template_id", sa.BigInteger),
    sa.column("field_key", sa.String),
    sa.column("label", sa.String),
    sa.column("scope", sa.String),
    sa.column("data_type", sa.String),
    sa.column("required", sa.Boolean),
    sa.column("column_order", sa.Integer),
    sa.column("validation_rule", sa.String),
    sa.column("region_x", sa.Float),
    sa.column("region_y", sa.Float),
    sa.column("region_width", sa.Float),
    sa.column("region_height", sa.Float),
)


def upgrade() -> None:
    op.bulk_insert(roles_table, [{"code": code, "name": name} for code, name in ROLES])
    op.bulk_insert(departments_table, [{"code": code, "name": name} for code, name in DEPARTMENTS])
    op.bulk_insert(settings_table, [{"key": k, "value": v, "description": d} for k, v, d in SETTINGS])

    connection = op.get_bind()
    for template in TEMPLATES:
        template_id = connection.execute(
            templates_table.insert()
            .values(
                code=template["code"],
                name=template["name"],
                description=template["description"],
                quantity_field_key=template["quantity_field_key"],
            )
            .returning(templates_table.c.id)
        ).scalar_one()
        op.bulk_insert(fields_table, _field_rows(template_id, template["columns"]))


def downgrade() -> None:
    codes = [template["code"] for template in TEMPLATES]
    op.execute(templates_table.delete().where(templates_table.c.code.in_(codes)))  # fields cascade
    op.execute(settings_table.delete().where(settings_table.c.key.in_([key for key, _, _ in SETTINGS])))
    op.execute(departments_table.delete().where(departments_table.c.code.in_([code for code, _ in DEPARTMENTS])))
    op.execute(roles_table.delete().where(roles_table.c.code.in_([code for code, _ in ROLES])))


def _field_rows(template_id: int, columns: list[tuple]) -> list[dict]:
    key, label, data_type, required = MONTH_FIELD
    x, y, width, height = MONTH_REGION
    rows = [_field(template_id, key, label, "HEADER", data_type, required, 0, x, y, width, height)]

    column_width = (TABLE_RIGHT - TABLE_LEFT) / len(columns)
    for order, (key, label, data_type, required) in enumerate(columns, start=1):
        x = TABLE_LEFT + (order - 1) * column_width
        rows.append(_field(template_id, key, label, "LINE", data_type, required, order, x, TABLE_TOP, column_width, TABLE_HEIGHT))
    return rows


def _field(template_id, key, label, scope, data_type, required, order, x, y, width, height) -> dict:
    return {
        "template_id": template_id,
        "field_key": key,
        "label": label,
        "scope": scope,
        "data_type": data_type,
        "required": required,
        "column_order": order,
        "validation_rule": "NONE",
        "region_x": round(x, 4),
        "region_y": round(y, 4),
        "region_width": round(width, 4),
        "region_height": round(height, 4),
    }
