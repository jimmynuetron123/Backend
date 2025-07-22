from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
from geopy.geocoders import Nominatim
import requests
from io import BytesIO
from openpyxl import Workbook
import csv
import time

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --------------------
# CONFIG & HELPERS
# --------------------

cdc_files = {
    "2024": "PLACES__Local_Data_for_Better_Health__Census_Tract_Data_2024_release_20250624.csv",
    "2023": "PLACES__Local_Data_for_Better_Health__Census_Tract_Data_2023_release_20250624.csv",
    "2022": "PLACES__Local_Data_for_Better_Health__Census_Tract_Data_2022_release_20250624.csv",
    "2021": "PLACES__Local_Data_for_Better_Health__Census_Tract_Data_2021_release_20250624.csv",
    "2020": "PLACES__Local_Data_for_Better_Health__Census_Tract_Data_2020_release_20250624.csv",
    "2019": "PLACES__Local_Data_for_Better_Health__Census_Tract_Data_2019_release_20250624.csv"
}


selectedFile = 'your_file.csv'

CENSUS_API_KEY = "d2597da23235cd440c54bc34235b9a6c8a43033d"

geolocator = Nominatim(user_agent="geoapi")

def build_census_url(year, table_code):
    if table_code.startswith("S") and int(year) >= 2016:
        return f"https://api.census.gov/data/{year}/acs/acs5/subject"
    elif table_code.startswith("DP"):
        return f"https://api.census.gov/data/{year}/acs/acs5/profile"
    elif table_code.startswith(("P", "H")):
        return f"https://api.census.gov/data/2020/dec/dhc"
    else:
        return f"https://api.census.gov/data/{year}/acs/acs5"

def clean_value(val):
    if val in (None, '', '-666666666', '-888888888'):
        return None
    return val

def format_percent(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        value = float(value)
        # Sanity check: if value > 100, probably bad data → cap it
        if value > 100:
            print(f"⚠️ Warning: unusually high percentage {value}, capping to 100")
            value = 100
        return f"{value:.1f}%"
    except ValueError:
        return value






# --------------------
# DATA FUNCTIONS
# --------------------

def get_cdc_file(year):
    year = str(year).strip()
    file = cdc_files.get(year)
    if not file:
        print(f"⚠️ No CDC file configured for year {year}")
        return pd.DataFrame()
    try:
        df = pd.read_csv(file, dtype=str)
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "")
        print(f"✅ Loaded CDC file for {year}")
        return df
    except Exception as e:
        print(f"❌ Failed to load CDC file {year}: {e}")
        return pd.DataFrame()

def get_all_cdc_data_for_tract(tractfips, cdc_df):
    if cdc_df.empty or "locationid" not in cdc_df.columns:
        return pd.DataFrame()
    tract_search = str(tractfips).strip()[:11]
    cdc_df["locationid"] = cdc_df["locationid"].astype(str).str.strip()
    filtered = cdc_df[cdc_df["locationid"] == tract_search]
    return filtered

def get_lat_lon_and_tract(address):
    try:
        location = geolocator.geocode(address, timeout=10)
        if not location:
            return None, None, None
        lat, lon = location.latitude, location.longitude
        response = requests.get(
            "https://geocoding.geo.census.gov/geocoder/geographies/coordinates",
            params={
                "x": lon,
                "y": lat,
                "benchmark": "Public_AR_Current",
                "vintage": "Current_Current",
                "layers": "Census Tracts",
                "format": "json"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            geo = data["result"]["geographies"]["Census Tracts"][0]
            tract_code = f"{geo['STATE']}{geo['COUNTY']}{geo['TRACT'].zfill(6)}"
            return lat, lon, tract_code
    except Exception as e:
        print(f"❌ Error processing address {address}: {e}")
    return None, None, None


#2023
def get_dp02_data(state, county, tract, api_key, census_year):
    try:
        vars_dp02 = {
            "DP02_0001M": "Total Households",
            "DP02_0002PE": "Married-Couple Households (%)",
            "DP02_0012PE": "Female Householder, No Spouse (%)",
            "DP02_0153PE": "Households with a Computer (%)",
            "DP02_0154PE": "Households with Broadband (%)",
            "DP02_0116PE": "Speak Spanish at Home (%)",
            "DP02_0118PE": "Speak Other Indo-European Languages at Home (%)",
            "DP02_0120PE": "Speak Asian & Pacific Island Languages at Home (%)",
            "DP02_0122PE": "Speak Other Languages at Home (%)",
        }

        url = build_census_url(census_year, "DP02")
        params = {
            "get": ",".join(vars_dp02.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        values = dict(zip(json_data[0], json_data[1]))


        return {
            label: format_percent(clean_value(values.get(code))) 
            if code.endswith('PE') and 'Total Households' not in label 
            else clean_value(values.get(code))
            for code, label in vars_dp02.items()
        }



    except Exception as e:
        print(f"❌ Failed to fetch DP02 data: {e}")
        return {}

#2022
def get_dp02_data(state, county, tract, api_key, census_year):
    try:
        vars_dp02 = {
            "DP02_0001E": "Total Households",
            "DP02_0002PE": "Married-Couple Households (%)",
            "DP02_0012PE": "Female Householder, No Spouse (%)",
           # "DP02PR_0017PE": "Married-Couple Families (%)",
            "DP02_0153PE": "Households with a Computer (%)",
            "DP02_0154PE": "Households with Broadband (%)",
            "DP02_0116PE": "Speak Spanish at Home (%)",
            "DP02_0118PE": "Speak Other Indo-European Languages at Home (%)",
            "DP02_0120PE": "Speak Asian & Pacific Island Languages at Home (%)",
            "DP02_0122PE": "Speak Other Languages at Home (%)",
        
        }

        url = build_census_url(census_year, "DP02")


        params = {
            "get": ",".join(vars_dp02.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        values = dict(zip(res.json()[0], res.json()[1]))

        return {label: clean_value(values.get(code)) for code, label in vars_dp02.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch expanded DP02 data: {e}")
        return {}

#2021/2020
def get_dp02_data(state, county, tract, api_key, census_year):
    try:
        vars_dp02 = {
            "DP02_0001E": "Total Households",
            "DP02_0002PE": "Married-Couple Households (%)",
            "DP02_0012PE": "Female Householder, No Spouse (%)",
           # "DP02PR_0017PE": "Married-Couple Families (%)",
            "DP02_0153PE": "Households with a Computer (%)",
            "DP02_0116PE": "Speak Spanish at Home (%)",
            "DP02_0122PE": "Speak Other Languages at Home (%)"
        
        }

        url = build_census_url(census_year, "DP02")


        params = {
            "get": ",".join(vars_dp02.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        values = dict(zip(res.json()[0], res.json()[1]))

        return {label: clean_value(values.get(code)) for code, label in vars_dp02.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch expanded DP02 data: {e}")
        return {}

#2019
def get_dp02_data(state, county, tract, api_key, census_year):
    try:
        vars_dp02 = {
            "DP02_0001E": "Total Households",
            "DP02_0002PE": "Married-Couple Households (%)",
            "DP02_0012PE": "Female Householder, No Spouse (%)",
           # "DP02PR_0017PE": "Married-Couple Families (%)",
            "DP02_0152PE": "Households with a Computer (%)",
            "DP02_0115PE": "Speak Spanish at Home (%)",
            "DP02_0121PE": "Speak Other Languages at Home (%)"
        
        }

        url = f"https://api.census.gov/data/{census_year}/acs/acs5/profile"


        params = {
            "get": ",".join(vars_dp02.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        values = dict(zip(res.json()[0], res.json()[1]))

        return {label: clean_value(values.get(code)) for code, label in vars_dp02.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch expanded DP02 data: {e}")
        return {}   

#2018/2017/2016/2015/2014/2013
def get_dp02_data(state, county, tract, api_key, census_year):
    try:
        vars_dp02 = {
            "DP02_0001E": "Total Households",
            "DP02_0004PE": "Married-Couple Households (%)",
            "DP02_0008PE": "Female Householder, No Spouse (%)",
           # "DP02PR_0017PE": "Married-Couple Families (%)",
            "DP02_0151PE": "Households with a Computer (%)",
            "DP02_0114PE": "Speak Spanish at Home (%)",
            "DP02_0120PE": "Speak Other Languages at Home (%)"
        
        }

        url = f"https://api.census.gov/data/{census_year}/acs/acs5/profile"


        params = {
            "get": ",".join(vars_dp02.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        values = dict(zip(res.json()[0], res.json()[1]))

        return {label: clean_value(values.get(code)) for code, label in vars_dp02.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch expanded DP02 data: {e}")
        return {}
    
#2012/2011/2010
def get_dp02_data(state, county, tract, api_key, census_year):
    try:
        vars_dp02 = {
            "DP02_0001E": "Total Households",
            "DP02_0004PE": "Married-Couple Households (%)",
            "DP02_0008PE": "Female Householder, No Spouse (%)",
           # "DP02PR_0017PE": "Married-Couple Families (%)",
            "DP02_0114PE": "Speak Spanish at Home (%)",
            "DP02_0120PE": "Speak Other Languages at Home (%)"
        
        }

        url = f"https://api.census.gov/data/{census_year}/acs/acs5/profile"


        params = {
            "get": ",".join(vars_dp02.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        values = dict(zip(res.json()[0], res.json()[1]))

        return {label: clean_value(values.get(code)) for code, label in vars_dp02.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch expanded DP02 data: {e}")
        return {} 

#2023/2022/2021/2020/2019/2018/2017/2016/2015/2014/2013/2012/2011/2010
def get_s2502_data(state, county, tract, api_key, census_year):
    try:
        vars_s2502 = {
            "S2502_C01_018E": "Less than High School"
        }

        url = build_census_url(census_year, "S2502")

        params = {
            "get": ",".join(vars_s2502.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        print(f"    Calling ACS S2502 (Social Characteristics - Housing): state={state}, county={county}, tract={tract}")
        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        json_response = res.json()
        

        data = dict(zip(json_response[0], json_response[1]))

        return {label: clean_value(data.get(code)) for code, label in vars_s2502.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch S2502 data: {e}")
        return {} 

#2020
def get_p9_data(state, county, tract, api_key, census_year):

    try:
        vars_p9 = {
            "P9_002N": "Hispanic or Latino"
        }

        url = build_census_url(census_year, "P9_002N")

        params = {
            "get": ",".join(vars_p9.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        print(f"    Calling ACS P9 (Hispanic & Latino): state={state}, county={county}, tract={tract}")
        res = requests.get(url, params=params)
        res.raise_for_status()
        json_response = res.json()
        json_data = res.json()

        data = dict(zip(json_response[0], json_response[1]))

        return {label: clean_value(data.get(code)) for code, label in vars_p9.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch P9 data: {e}")
        return {}

def get_h1_data(state, county, tract, api_key, census_year):

    try:
        vars_h1 = {
            "H1_001N": "Housing Units"
        }

        url = build_census_url(census_year, "H1_001N")

        params = {
            "get": ",".join(vars_h1.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        print(f"    Calling ACS H1 Housing Units: state={state}, county={county}, tract={tract}")
        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        json_response = res.json()

        data = dict(zip(json_response[0], json_response[1]))

        return {label: clean_value(data.get(code)) for code, label in vars_h1.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch H1 data: {e}")
        return {}

def get_s2902_data(state, county, tract, api_key, census_year):
    try:
        vars_s2902 = {
            "S2902_C01_011E": "Some College, No Degree"
        }

        url = build_census_url(census_year, "S2902")

        params = {
            "get": ",".join(vars_s2902.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        print(f"    Calling ACS S2902 (Selected Social Characteristics): state={state}, county={county}, tract={tract}")
        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        json_response = res.json()

        data = dict(zip(json_response[0], json_response[1]))

        return {label: clean_value(data.get(code)) for code, label in vars_s2902.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch S2902 data: {e}")
        return {}


#2023/2022/2021/2020/2019/2018/2017/2016/2015/2014/2013/2012
def get_s1701_poverty_data(state, county, tract, api_key, census_year):
    try:
        vars_s1701 = {
            "S1701_C03_001E": "Poverty Rate - Total",
           
        }

        url = build_census_url(census_year, "S1701")

        params = {
            "get": ",".join(vars_s1701.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        data = dict(zip(res.json()[0], res.json()[1]))

        return {label: clean_value(data.get(code)) for code, label in vars_s1701.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch S1701 poverty data: {e}")
        return {}

#2023/2022/2021/2020/2019/2018/2017/2016/2015
def get_s2701_data(state, county, tract, api_key, census_year):
    try:
        vars_s2701 = {
            "S2701_C02_001E": "With Any Health Insurance"
            
        }

        url = build_census_url(census_year, "S2701")


        params = {
            "get": ",".join(vars_s2701.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        values = dict(zip(res.json()[0], res.json()[1]))

        return {label: clean_value(values.get(code)) for code, label in vars_s2701.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch S2701 insurance data: {e}")
        return {}

#2014/2013
def second_s2701_data(state, county, tract, api_key, census_year):
    try:
        vars_s2701 = {
            "S2701_C04_001E": "Without Health Insurance"
        }

        # Choose the correct URL depending on the year
        if census_year in ["2013", "2014", "2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023"]:
            url = f"https://api.census.gov/data/{census_year}/acs/acs5/subject"
        else:
            print(f"    ❌ Year {census_year} not supported for S2701 subject tables.")
            return {}

        params = {
            "get": ",".join(vars_s2701.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        headers, values = res.json()[0], res.json()[1]
        data = dict(zip(headers, values))

        return {label: clean_value(data.get(code)) for code, label in vars_s2701.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch S2701 insurance data: {e}")
        return {}

def get_b19001_data(state, county, tract, api_key, census_year):
    try:
        brackets = {
            "B19001_002E": "Less than $10,000",
            "B19001_003E": "$10,000 to $14,999",
            "B19001_004E": "$15,000 to $19,999",
            "B19001_005E": "$20,000 to $24,999",
            "B19001_006E": "$25,000 to $29,999",
            "B19001_007E": "$30,000 to $34,999",
            "B19001_008E": "$35,000 to $39,999",
            "B19001_009E": "$40,000 to $44,999",
            "B19001_010E": "$45,000 to $49,999",
            "B19001_011E": "$50,000 to $59,999",
            "B19001_012E": "$60,000 to $74,999",
            "B19001_013E": "$75,000 to $99,999",
            "B19001_014E": "$100,000 to $124,999",
            "B19001_015E": "$125,000 to $149,999",
            "B19001_016E": "$150,000 to $199,999",
            "B19001_017E": "$200,000 or more"
        }

        vars_income = ["B19001_001E"] + list(brackets.keys())

        url = build_census_url(census_year, "B19001")

        params = {
            "get": ",".join(vars_income),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        

        values = dict(zip(json_data[0], json_data[1]))


        if values.get("B19001_001E") in ("0", None):
            print(f"    ⚠️ Tract {tract} has no households reported (B19001_001E = 0).")
            return {"Total Households (B19001)": 0}

        result = {
            "Total Households (B19001)": clean_value(values.get("B19001_001E"))
        }

        for code, label in brackets.items():
            result[label] = clean_value(values.get(code))

        return result

    except Exception as e:
        print(f"    ❌ Failed to fetch full income breakdown: {e}")
        return {}

#2023/2017/2012/2010
def get_dp03_data(state, county, tract, api_key, census_year):
    try:
        vars_dp03 = {
            "DP03_0005PE": "Unemployment Rate (%)",
            "DP03_0001PE": "Employment Rate (%)",
            "DP03_0018E": "Mean Commute Time (min)",
            "DP03_0092E": "Median Earnings (Male FT)",
            "DP03_0074E": "Households w/ SNAP"
            #"DP04_0058PE": "Households w/ No Vehicle (%)"
        }

        url = build_census_url(census_year, "DP03")
        params = {
            "get": ",".join(vars_dp03.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        values = dict(zip(res.json()[0], res.json()[1]))

        return {label: clean_value(values.get(code)) for code, label in vars_dp03.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch DP03 data: {e}")
        return {}

def get_dp04_vehicle_data(state, county, tract, api_key, census_year):
    try:
        vars_dp04 = {
            "DP04_0058PE": "Households w/ No Vehicle (%)"
            
        }

        url = f"https://api.census.gov/data/{census_year}/acs/acs5/profile"

        params = {
            "get": ",".join(vars_dp04.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        print(f"    Calling ACS DP04 (Transportation/Vehicle): state={state}, county={county}, tract={tract}")
        res = requests.get(url, params=params)
        res.raise_for_status()
        json_data = res.json()
        json_response = res.json()

        data = dict(zip(json_response[0], json_response[1]))

        return {label: clean_value(data.get(code)) for code, label in vars_dp04.items()}

    except Exception as e:
        print(f"    ❌ Failed to fetch DP04 vehicle data: {e}")
        return {}

def get_s0101_data_2015(state, county, tract, api_key, census_year):
    try:
        vars_s0101 = {
            
            "S0101_C01_030E": "Median Age (2015)",  #2015
            "S0101_C03_001E": "Female Population (2015)", #2015
            
        }

        url = build_census_url(census_year, "S0101")


        params = {
            "get": ",".join(vars_s0101.keys()),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        print(f"    Calling 2015 ACS S0101 (Age & Sex): state={state}, county={county}, tract={tract}")
        res = requests.get(url, params=params)

        if res.status_code == 400:
            print("    ⚠️ S0101 2015 data not available for this tract.")
            return {}

        res.raise_for_status()
        json_data = res.json()
        json_response = res.json()

        # 🔍 Print the raw API response for inspection
        print("S0101 2015 raw data:", json_response)

        data = dict(zip(json_response[0], json_response[1]))

        return {
            "Median Age (S0101)": clean_value(data.get("S0101_C01_030E")),
            "Female Population (S0101)": clean_value(data.get("S0101_C03_001E")),
        }

    except Exception as e:
        print(f"    ❌ Failed to fetch S0101 data: {e}")
        return {}


def get_s0101_data(state, county, tract, api_key, census_year):
    try:
        vars_s0101 = {
            "S0101_C01_001E": "Total Poulation",
            "S0101_C01_032E": "Median Age",
            "S0101_C03_001E": "Male Population",
            "S0101_C05_001E": "Female Population"
        }

        url = build_census_url(census_year, "S0101")

        params = {
            "get": ",".join(vars_s0101),
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": api_key
        }

        print(f"    Calling ACS S0101 (Age & Sex): state={state}, county={county}, tract={tract}")
        res = requests.get(url, params=params)

        if res.status_code == 400:
            print("    ⚠️ S0101 data not available for this tract.")
            return {}

        res.raise_for_status()
        json_data = res.json()
        json_response = res.json()

        # 🔍 Print the raw API response for inspection
        print("S0101 raw data:", json_response)

        data = dict(zip(json_response[0], json_response[1]))

        return {
            "Total Poulation(S0101)": clean_value(data.get("S0101_C01_001E")),
            "Median Age (S0101)": clean_value(data.get("S0101_C01_032E")),
            "Male Population (S0101)": clean_value(data.get("S0101_C03_001E")),
            "Female Population (S0101)": clean_value(data.get("S0101_C05_001E"))
        }

    except Exception as e:
        print(f"    ❌ Failed to fetch S0101 data: {e}")
        return {}




def generate_excel(all_results):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active

    # Collect all unique metric keys
    metric_keys = set()
    for result in all_results:
        metric_keys.update(result["GeneralInfo"].keys())
        metric_keys.update(result["CDC"].keys())
        metric_keys.update(result["Census"].keys())

    # Sort keys for consistent column order
    sorted_keys = sorted(metric_keys)

    # Write header
    ws.append(sorted_keys)

    # Write one row per address
    for result in all_results:
        row_data = {}
        row_data.update(result["GeneralInfo"])
        row_data.update(result["CDC"])
        row_data.update(result["Census"])

        row = [row_data.get(k, "") for k in sorted_keys]
        ws.append(row)

    # Output to bytes
    from io import BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output




# --------------------
# API ROUTES
# --------------------

@app.route("/")
def home():
    return "✅ API is running. POST to /api/tract"


@app.route("/api/tract", methods=["POST", "OPTIONS"])
def get_data():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight successful"}), 200

    data = request.get_json()
    if not data or "year" not in data:
        return jsonify({"error": "❌ Missing 'year' in request body."}), 400

    selected_year = str(data.get("year")).strip()
    data_type = data.get("dataType", "CDC")
    census_year = selected_year

    # Collect addresses: single input + optional batch input
    addresses = []
    single_address = data.get("input", "").strip()
    if single_address:
        addresses.append(single_address)

    excel_data = data.get("excelData", [])  # ✅ define safely

    if isinstance(excel_data, list) and excel_data:
        print(f"📦 Received Excel data with {len(excel_data)} rows")
        addresses.extend([
    row.get("Address") or row.get("address") or row.get("ADDRESS", "").strip()
    for row in excel_data
    if row.get("Address") or row.get("address") or row.get("ADDRESS")
    ])


    if not addresses:
        return jsonify({"error": "❌ No valid addresses provided."}), 400

    all_results = []

    for addr in addresses:
        if not addr:
            continue

        print(f"\n📍 Processing: {addr}")
        lat, lon, tract_code = get_lat_lon_and_tract(addr)
        if not tract_code:
            print(f"❌ Failed to get tract for address: {addr}")
            continue

        # ... rest of your processing code ...


        response_payload = {
            "GeneralInfo": {
                "Year": selected_year,
                "Address": addr,
                "Latitude": lat,
                "Longitude": lon,
                "TractFIPS": tract_code
            },
            "CDC": {},
            "Census": {}
        }

        # --- CDC data ---
        if data_type in ["CDC", "Both"]:
            cdc_df = get_cdc_file(selected_year)
            df = get_all_cdc_data_for_tract(tract_code, cdc_df)
            if not df.empty:
                for _, r in df.iterrows():
                    measure = r["measure"].strip()
                    value = f"{r['data_value']}{r['data_value_unit'] or ''}"
                    response_payload["CDC"][measure] = value
            else:
                print("⚠️ No CDC data found for this tract.")

        # --- Census data ---
        if data_type in ["CENSUS", "Both"]:
            state = tract_code[:2]
            county = tract_code[2:5]
            tract = tract_code[5:]

        census_resultB19001 = get_b19001_data(state, county, tract, CENSUS_API_KEY, census_year)
        census_result = get_dp02_data(state, county, tract, CENSUS_API_KEY, census_year)

        census_resultS2502 = get_s2502_data(state, county, tract, CENSUS_API_KEY, census_year)
        census_resultS0101 = get_s0101_data(state, county, tract, CENSUS_API_KEY, census_year)

        if census_year in ["2023", "2017", "2012", "2010"]:
            census_resultDp03 = get_dp03_data(state, county, tract, CENSUS_API_KEY, census_year)
            response_payload["Census"].update(census_resultDp03 or {})

        if census_year == "2015":
            census_resultS0101_2015 = get_s0101_data_2015(state, county, tract, CENSUS_API_KEY, census_year)
            response_payload["Census"].update(census_resultS0101_2015 or {})

        if census_year >= "2015":
            census_resultDp04 = get_dp04_vehicle_data(state, county, tract, CENSUS_API_KEY, census_year)
            census_resultS2701 = get_s2701_data(state, county, tract, CENSUS_API_KEY, census_year)
            response_payload["Census"].update(census_resultDp04 or {})
            response_payload["Census"].update(census_resultS2701 or {})

        if census_year in ["2014", "2013"]:
            census_second_resultS2701 = second_s2701_data(state, county, tract, CENSUS_API_KEY, census_year)
            response_payload["Census"].update(census_second_resultS2701 or {})

        if census_year >= "2018":
            census_resultS2902 = get_s2902_data(state, county, tract, CENSUS_API_KEY, census_year)
            response_payload["Census"].update(census_resultS2902 or {})

        if census_year >= "2012":
            census_resultS1701 = get_s1701_poverty_data(state, county, tract, CENSUS_API_KEY, census_year)
            response_payload["Census"].update(census_resultS1701 or {})

        if census_year == "2020":
            census_resultsP9 = get_p9_data(state, county, tract, CENSUS_API_KEY, census_year)
            census_resultsH1 = get_h1_data(state, county, tract, CENSUS_API_KEY, census_year)
            response_payload["Census"].update(census_resultsP9 or {})
            response_payload["Census"].update(census_resultsH1 or {})

        # Always include the general census results
        response_payload["Census"].update(census_resultB19001 or {})
        response_payload["Census"].update(census_result or {})
        response_payload["Census"].update(census_resultS2502 or {})
        response_payload["Census"].update(census_resultS0101 or {})

        percentage_columns = [
            "Unemployment Rate (%)",
            "Employment Rate (%)",
            "Married-Couple Households (%)",
            "Female Householder, No Spouse (%)",
            "Married-Couple Families (%)",
            "Households w/ No Vehicle (%)",
            "Households with a Computer (%)",
            "Households with Broadband (%)",
            "Speak Spanish at Home (%)",
            "Speak Other Indo-European Languages at Home (%)",
            "Speak Asian & Pacific Island Languages at Home (%)",
            "Speak Other Languages at Home (%)"
        ]

        for col in percentage_columns:
            if col in response_payload["Census"]:
                val = response_payload["Census"][col]
                response_payload["Census"][col] = format_percent(val)


        all_results.append(response_payload)

    if not all_results:
        return jsonify({"error": "❌ No valid addresses processed."}), 400

    excel_file = generate_excel(all_results)
    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='data_output.xlsx'
    )
    
    return jsonify({"results": all_results}), 200




@app.route("/api/download", methods=["POST"])
def download_excel():
    data = request.get_json()
    if not data:
        return jsonify({"error": "❌ No data provided to generate Excel."}), 400
    try:
        excel_file = generate_excel(data)
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='data_output.xlsx'
        )
    except Exception as e:
        print(f"❌ Excel generation error: {e}")
        return jsonify({"error": "❌ Failed to generate Excel file."}), 500


# --------------------
# RUN APP
# --------------------

if __name__ == "__main__":
    print("✅ Flask app is running on http://0.0.0.0:5050")
    app.run(host="0.0.0.0", port=5050, debug=True)
