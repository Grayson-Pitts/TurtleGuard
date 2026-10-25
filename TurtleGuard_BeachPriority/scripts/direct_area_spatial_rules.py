"""Approximate direct monitoring extents, for linking to actual FWC beach GIS lines.
No string matching to the FWC Beach field. These rectangles are APPROXIMATIONS,
not FWC verified survey boundaries and must be labeled accordingly.
"""
# (region_id, set_of_counties, lon_min, lon_max, lat_min, lat_max)
# More specific beach areas checked before broader county areas.
RULES=[
    ('Boca Raton',{'palmbeach'},-80.115,-80.035,26.325,26.425),
    ('Lido Key',{'sarasota'},-82.610,-82.555,27.298,27.350),
    ('Siesta Key',{'sarasota'},-82.610,-82.508,27.205,27.310),
    ('Longboat Key',{'sarasota','manatee'},-82.740,-82.585,27.335,27.525),
    ('Casey Key',{'sarasota'},-82.545,-82.455,27.132,27.250),
    ('Venice',{'sarasota'},-82.490,-82.395,27.028,27.147),
    ('Canaveral National Seashore',{'brevard','volusia'},-80.850,-80.530,28.590,28.955),
    ('Volusia County',{'volusia'},-81.100,-80.620,28.945,29.460),
]

def approximate_direct_region(county,geometry):
    typ=geometry.get('type')
    coords=geometry.get('coordinates',[])
    lines=[coords] if typ=='LineString' else coords if typ=='MultiLineString' else []
    points=[(p[0],p[1]) for line in lines for p in line]
    if not points:return None
    lon=sum(p[0] for p in points)/len(points)
    lat=sum(p[1] for p in points)/len(points)
    for name,counties,lo1,hi1,la1,ha1 in RULES:
        if county in counties and lo1<=lon<=hi1 and la1<=lat<=ha1:return name
    return None
