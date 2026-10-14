"""Create or update the "Taylor Mobile POC" dashboard (stdlib only, local POC).

Prereq: poc/taylor_dummy_data.sql loaded into the examples DB.
Usage: python3 poc/setup_taylor_dashboard.py   -> prints the embed UUID
"""

import http.cookiejar
import json
import os
import urllib.parse
import urllib.request

SUPERSET_URL = os.environ.get("SUPERSET_URL", "http://localhost:8088")
# Docker dev defaults; dummy POC data only.
SUPERSET_USER = os.environ.get("SUPERSET_USER", "admin")
SUPERSET_PASSWORD = os.environ.get("SUPERSET_PASSWORD", "admin")
DATABASE_ID = 1  # "examples"
DASHBOARD_TITLE = "Taylor Mobile POC"
ALLOWED_DOMAINS = ["http://localhost:8000", "http://192.168.18.14:8000"]

DARK_TEAL, LIGHT_TEAL, ORANGE = "#327B7E", "#69D2D7", "#F7BC35"
SALMON, PURPLE = "#F5967C", "#8D48BF"
LABEL_COLORS = {
    "Scope 1": DARK_TEAL,
    "Scope 2": ORANGE,
    "Scope 3": LIGHT_TEAL,
    "Rest of World": DARK_TEAL,
    "Singapore": LIGHT_TEAL,
    "Manufacturing": DARK_TEAL,
    "Logistics": LIGHT_TEAL,
    "Corporate": ORANGE,
    "Northwind Holdings": DARK_TEAL,
    "Bluecrest Industries": LIGHT_TEAL,
    "Harbor Supply Co": ORANGE,
    "Meridian Logistics": SALMON,
    "Solace Energy Pte Ltd": PURPLE,
}

_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)
_headers = {"Content-Type": "application/json", "Referer": SUPERSET_URL}


def api(method, path, data=None):
    req = urllib.request.Request(
        SUPERSET_URL + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=_headers,
        method=method,
    )
    with _opener.open(req, timeout=60) as resp:
        return json.loads(resp.read() or b"{}")


def find(resource, col, value):
    q = urllib.parse.quote(
        f"(filters:!((col:{col},opr:eq,value:'{value}')),page_size:100)"
    )
    return api("GET", f"/api/v1/{resource}/?q={q}")["result"]


def login():
    token = api(
        "POST",
        "/api/v1/security/login",
        {"username": SUPERSET_USER, "password": SUPERSET_PASSWORD,
         "provider": "db", "refresh": True},
    )["access_token"]
    _headers["Authorization"] = f"Bearer {token}"
    _headers["X-CSRFToken"] = api("GET", "/api/v1/security/csrf_token/")["result"]


def dataset(table):
    existing = [d for d in find("dataset", "table_name", table)
                if d["database"]["id"] == DATABASE_ID]
    if existing:
        return existing[0]["id"]
    return api("POST", "/api/v1/dataset/",
               {"database": DATABASE_ID, "schema": "public", "table_name": table})["id"]


def metric(column, aggregate, label):
    return {"expressionType": "SIMPLE", "column": {"column_name": column},
            "aggregate": aggregate, "label": label}


EMISSIONS = metric("emissions_kg", "SUM", "Emissions (kg)")
LEGEND = {"show_legend": True, "legendType": "scroll", "legendOrientation": "bottom"}


def big_number(m):
    return {"metric": m, "y_axis_format": "SMART_NUMBER", "header_font_size": 0.4,
            "subheader_font_size": 0.15, "time_range": "No filter"}


def donut(groupby):
    return {"groupby": [groupby], "metric": EMISSIONS, "donut": True,
            "show_total": True, "show_labels": True, "label_type": "key_percent",
            "labels_outside": True, "label_line": True, "innerRadius": 55,
            "outerRadius": 75, "number_format": "SMART_NUMBER",
            "sort_by_metric": True, "row_limit": 100, "time_range": "No filter",
            **LEGEND}


def bar(x_axis, groupby, m, stack=True, horizontal=False, **extra):
    params = {"x_axis": x_axis, "groupby": [groupby], "metrics": [m],
              "xAxisForceCategorical": True, "x_axis_sort_asc": True,
              "y_axis_format": "SMART_NUMBER", "orientation":
              "horizontal" if horizontal else "vertical", "row_limit": 10000,
              "time_range": "No filter", "rich_tooltip": True, **LEGEND, **extra}
    if stack:
        params.update({"stack": "Stack", "show_value": True, "only_total": True})
    return params


def chart_specs(ds):
    water_emission = metric("water_emission", "SUM", "Water emission")
    water_usage = metric("water_usage_m3", "SUM", "Water (m³)")
    return [
        ("Total Emissions (Scope 1, 2 and 3)", "big_number_total", ds["emissions"],
         big_number(EMISSIONS)),
        ("Number of Assets", "big_number_total", ds["assets"],
         big_number(metric("asset_id", "COUNT_DISTINCT", "Number of Assets"))),
        ("Total Emissions", "pie", ds["emissions"], donut("scope")),
        ("Total Emissions Over Time", "echarts_timeseries_bar", ds["emissions"],
         bar("year", "scope", EMISSIONS)),
        ("Total Emissions Breakdown by Region", "pie", ds["emissions"],
         donut("region")),
        ("Total Emissions Breakdown by Division", "pie", ds["emissions"],
         donut("division")),
        ("Emission by Company", "echarts_timeseries_bar", ds["emissions"],
         bar("scope", "company", EMISSIONS)),
        ("Breakdown of Company Emissions", "echarts_timeseries_bar", ds["emissions"],
         bar("company", "scope", EMISSIONS, horizontal=True,
             x_axis_sort="sum")),
        ("Water Emission Over Time - By Company", "echarts_timeseries_bar",
         ds["water"], bar("year", "company", water_emission, stack=False)),
        ("Water Usage Over Time (m³) - By Company", "echarts_timeseries_bar",
         ds["water"], bar("year", "company", water_usage, stack=False)),
    ]


def upsert_chart(name, viz, ds_id, params, dashboard_id):
    body = {"slice_name": name, "viz_type": viz, "datasource_id": ds_id,
            "datasource_type": "table", "dashboards": [dashboard_id],
            "params": json.dumps({"viz_type": viz,
                                  "datasource": f"{ds_id}__table", **params})}
    existing = [c for c in find("chart", "slice_name", name)
                if dashboard_id in [d["id"] for d in c.get("dashboards", [])]]
    if existing:
        api("PUT", f"/api/v1/chart/{existing[0]['id']}", body)
        return existing[0]["id"]
    return api("POST", "/api/v1/chart/", body)["id"]


def layout(chart_ids, names):
    pos = {"DASHBOARD_VERSION_KEY": "v2",
           "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["TABS-main"]},
           "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [],
                       "parents": ["ROOT_ID"]},
           "TABS-main": {"type": "TABS", "id": "TABS-main", "children": ["TAB-overview"],
                         "parents": ["ROOT_ID"], "meta": {}},
           "TAB-overview": {"type": "TAB", "id": "TAB-overview", "children": [],
                            "parents": ["ROOT_ID", "TABS-main"],
                            "meta": {"text": "Overview", "defaultText": "Tab title",
                                     "placeholder": "Tab title"}}}
    tab_parents = ["ROOT_ID", "TABS-main", "TAB-overview"]
    # Two charts per desktop row; mobile consumption mode stacks them.
    rows = [([0, 1], 22), ([2, 3], 60), ([4, 5], 60), ([6, 7], 60), "Water",
            ([8, 9], 60)]
    for n, row in enumerate(rows):
        if row == "Water":
            pos["HEADER-water"] = {
                "type": "HEADER", "id": "HEADER-water", "children": [],
                "parents": tab_parents,
                "meta": {"text": "Water", "headerSize": "MEDIUM_HEADER",
                         "background": "BACKGROUND_TRANSPARENT"}}
            pos["TAB-overview"]["children"].append("HEADER-water")
            continue
        indexes, height = row
        row_id = f"ROW-{n}"
        pos[row_id] = {"type": "ROW", "id": row_id, "children": [],
                       "parents": tab_parents,
                       "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        pos["TAB-overview"]["children"].append(row_id)
        for i in indexes:
            chart_key = f"CHART-{chart_ids[i]}"
            pos[chart_key] = {"type": "CHART", "id": chart_key, "children": [],
                              "parents": [*tab_parents, row_id],
                              "meta": {"chartId": chart_ids[i], "width": 6,
                                       "height": height, "sliceName": names[i]}}
            pos[row_id]["children"].append(chart_key)
    return pos


def main():
    login()
    ds = {"emissions": dataset("poc_emissions"), "assets": dataset("poc_assets"),
          "water": dataset("poc_water")}
    existing = find("dashboard", "dashboard_title", DASHBOARD_TITLE)
    dashboard_id = (existing[0]["id"] if existing else
                    api("POST", "/api/v1/dashboard/",
                        {"dashboard_title": DASHBOARD_TITLE})["id"])
    specs = chart_specs(ds)
    chart_ids = [upsert_chart(name, viz, ds_id, params, dashboard_id)
                 for name, viz, ds_id, params in specs]
    metadata = {"color_scheme": "supersetColors", "label_colors": LABEL_COLORS,
                "native_filter_configuration": [], "cross_filters_enabled": True,
                "refresh_frequency": 0}
    api("PUT", f"/api/v1/dashboard/{dashboard_id}", {
        "dashboard_title": DASHBOARD_TITLE, "published": True,
        "position_json": json.dumps(layout(chart_ids, [s[0] for s in specs])),
        "json_metadata": json.dumps(metadata)})
    embedded = api("POST", f"/api/v1/dashboard/{dashboard_id}/embedded",
                   {"allowed_domains": ALLOWED_DOMAINS})["result"]
    print(json.dumps({"dashboard_id": dashboard_id, "charts": chart_ids,
                      "embed_uuid": embedded["uuid"]}))


if __name__ == "__main__":
    main()
