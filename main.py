import random
import json
import warnings
from time import localtime
from requests import get, post
from datetime import datetime, date
from zhdate import ZhDate
import sys
import os

# 忽略因第三方接口 SSL 证书过期产生的警告
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

def get_color():
    # 获取随机颜色
    return "#%06x" % random.randint(0, 0xFFFFFF)

def get_access_token():
    # appId
    app_id = config.get("app_id") or os.environ.get("APP_ID")
    # appSecret
    app_secret = config.get("app_secret") or os.environ.get("APP_SECRET")
    if not app_id or not app_secret:
        print("请在 config.json 或环境变量中配置 app_id 和 app_secret")
        sys.exit(1)
        
    post_url = ("https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={}&secret={}"
                .format(app_id, app_secret))
    try:
        response = get(post_url, timeout=15).json()
        if 'access_token' in response:
            return response['access_token']
        else:
            print(f"[FAIL] 获取access_token失败: errcode={response.get('errcode')}, errmsg={response.get('errmsg')}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] 获取access_token出错: {e}")
        sys.exit(1)

def get_weather_open_meteo(region):
    """使用 Open-Meteo 免费接口（无需 API Key）"""
    # 地理编码：城市名转经纬度
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={region}&count=1&language=zh&format=json"
    try:
        geo_res = get(geo_url, timeout=15).json()
        if not geo_res.get("results"):
            print(f"[WARN] Open-Meteo 未找到地区: {region}")
            return "未知", "未知", "未知", "未知", "未知", "未能找到该地区", region
        
        loc = geo_res["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        region_name = loc.get("name", region)
        
        # 获取天气
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
        res = get(weather_url, timeout=15).json()
        
        current = res["current_weather"]
        daily = res["daily"]
        
        # WMO Weather interpretation codes (WW)
        wmo_codes = {
            0: "晴", 1: "大部晴朗", 2: "部分多云", 3: "阴",
            45: "雾", 48: "雾", 51: "细雨", 53: "细雨", 55: "细雨",
            61: "小雨", 63: "中雨", 65: "大雨",
            71: "小雪", 73: "中雪", 75: "大雪",
            80: "阵雨", 81: "阵雨", 82: "阵雨",
            95: "雷阵雨"
        }
        weather = wmo_codes.get(current["weathercode"], "多云")
        temp = f"{current['temperature']}°C"
        max_temp = f"{daily['temperature_2m_max'][0]}°C"
        min_temp = f"{daily['temperature_2m_min'][0]}°C"
        
        # 风向转换
        deg = current["winddirection"]
        directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        wind_dir = directions[int((deg + 22.5) / 45) % 8] + "风"
        
        # 随机温馨提示
        tips_list = [
            "记得多喝温水，照顾好自己呀！",
            "不管天气如何，我的心都和你在一起 ❤️",
            "今天也要加油，你是最棒的宝贝！",
            "出门记得检查随身物品，别丢三落四哒 ~",
            "你是我的今天，也是我的每一个明天。",
            "想你的时候，连风都是甜的。",
            "愿你今天遇到的小事，都能带给你好心情。"
        ]
        tips = random.choice(tips_list)
        
        return weather, temp, max_temp, min_temp, wind_dir, tips, region_name
    except Exception as e:
        print(f"[WARN] Open-Meteo 获取天气失败: {e}")
        return "未知", "未知", "未知", "未知", "未知", "天气服务暂时不可用", region

def get_weather(region):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
    }
    key = config.get("weather_key") or os.environ.get("WEATHER_KEY")
    
    # 如果没有配置 Key，则使用 Open-Meteo 免费接口（无需注册）
    if not key:
        return get_weather_open_meteo(region)

    # 原有的和风天气逻辑
    region_url = f"https://geoapi.qweather.com/v2/city/lookup?location={region}&key={key}"
    try:
        response = get(region_url, headers=headers, timeout=15).json()
        if response["code"] != "200":
            print(f"[WARN] 和风查询地区失败: {response.get('code')}")
            # 如果和风查询失败，尝试回退到免 Key 接口
            return get_weather_open_meteo(region)
            
        location_id = response["location"][0]["id"]
        region_name = response["location"][0]["name"]
    except Exception as e:
        print(f"[WARN] 和风查询地区出错: {e}")
        return get_weather_open_meteo(region)

    # 获取实时天气
    weather_url = f"https://devapi.qweather.com/v7/weather/now?location={location_id}&key={key}"
    forecast_url = f"https://devapi.qweather.com/v7/weather/3d?location={location_id}&key={key}"
    indices_url = f"https://devapi.qweather.com/v7/indices/1d?type=3&location={location_id}&key={key}"

    try:
        now_res = get(weather_url, headers=headers, timeout=15).json()
        forecast_res = get(forecast_url, headers=headers, timeout=15).json()
        indices_res = get(indices_url, headers=headers, timeout=15).json()

        weather = now_res["now"]["text"]
        temp = now_res["now"]["temp"] + "°C"
        wind_dir = now_res["now"]["windDir"]
        max_temp = forecast_res["daily"][0]["tempMax"] + "°C"
        min_temp = forecast_res["daily"][0]["tempMin"] + "°C"
        
        tips = "祝你今天有个好心情！"
        if indices_res["code"] == "200":
            tips = indices_res["daily"][0]["text"]

        return weather, temp, max_temp, min_temp, wind_dir, tips, region_name
    except Exception as e:
        print(f"[WARN] 和风获取天气详细信息出错: {e}")
        return get_weather_open_meteo(region)

def translate_en_to_zh(text):
    """使用 MyMemory 免费翻译接口将英文翻译成中文（失败则返回原文）"""
    if not text:
        return text
    try:
        url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|zh-CN"
        r = get(url, timeout=10)
        j = r.json()
        translated = j.get("responseData", {}).get("translatedText")
        if translated:
            return translated
    except:
        pass
    return text


def get_horoscope(constellation):
    if not constellation:
        return "保持乐观，好运常在！"
    
    # 中文星座 -> 英文星座映射
    constellation_map = {
        "白羊座": "aries", "金牛座": "taurus", "双子座": "gemini", "巨蟹座": "cancer",
        "狮子座": "leo", "处女座": "virgo", "天秤座": "libra", "天蝎座": "scorpio",
        "射手座": "sagittarius", "摩羯座": "capricorn", "水瓶座": "aquarius", "双鱼座": "pisces"
    }
    sign_en = constellation_map.get(constellation)
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 方案一：vvhan 接口（服务器可能无法连接，尝试绕过过期 SSL）
    url_vvhan = f"https://api.vvhan.com/api/horoscope?type={constellation}&time=today"
    try:
        res = get(url_vvhan, headers=headers, timeout=10, verify=False).json()
        if res.get("success"):
            data = res["data"]
            return f"{data['type']}：{data['text']}"
    except:
        pass
    
    # 方案二：freehoroscopeapi 接口（英文，兜底并尝试翻译核心句）
    if sign_en:
        url_fallback = f"https://freehoroscopeapi.com/api/v1/get-horoscope/daily?sign={sign_en}"
        try:
            r = get(url_fallback, headers=headers, timeout=10)
            j = r.json()
            if j.get("data") and j["data"].get("horoscope"):
                en_text = j["data"]["horoscope"]
                # 只取第一句核心内容翻译，避免超出免费翻译接口 500 字符限制
                first_sentence = en_text.split(". ")[0].strip()
                if not first_sentence.endswith("."):
                    first_sentence += "."
                zh_text = translate_en_to_zh(first_sentence)
                return f"{constellation}：{zh_text}"
        except:
            pass
    
    # 方案三：预置中文运势文案（保证推送永远是中文且温馨）
    preset_horoscopes = [
        "今天是你闪闪发光的一天，保持微笑，好运自然来。",
        "无论遇到什么，都要相信自己，你比想象中更强大。",
        "今天的你值得所有的温柔与美好，记得照顾好自己。",
        "好运正在路上，保持好心情，一切都会顺顺利利。",
        "你是独一无二的存在，今天也要开心地做自己。",
        "愿今天的每一个小确幸，都能让你嘴角上扬。",
        "保持热爱，奔赴山海，今天会是充满惊喜的一天。",
        "你的努力都会被看见，今天也继续加油吧！",
        "今天适合给自己一个拥抱，你已经做得很好了。",
        "相信美好的事情即将发生，保持期待，保持热爱。"
    ]
    return f"{constellation}：{random.choice(preset_horoscopes)}"

def get_birthday(birthday, year, today):
    # 判断是否为农历生日（配置中在年份前加 r 表示农历，如 "r2002-07-28"）
    is_lunar = birthday.startswith("r")
    if is_lunar:
        # 农历生日格式 rYYYY-MM-DD，取月和日
        parts = birthday[1:].split("-")
        r_mouth = int(parts[1])
        r_day = int(parts[2])
        try:
            birthday_obj = ZhDate(year, r_mouth, r_day).to_datetime().date()
        except Exception:
            return "未知"
        birthday_month = birthday_obj.month
        birthday_day = birthday_obj.day
        year_date = date(year, birthday_month, birthday_day)
    else:
        parts = birthday.split("-")
        birthday_month = int(parts[1])
        birthday_day = int(parts[2])
        year_date = date(year, birthday_month, birthday_day)
    
    if today > year_date:
        if is_lunar:
            r_last_birthday = ZhDate((year + 1), r_mouth, r_day).to_datetime().date()
            birth_date = date((year + 1), r_last_birthday.month, r_last_birthday.day)
        else:
            birth_date = date((year + 1), birthday_month, birthday_day)
        birth_day = (birth_date - today).days
    elif today == year_date:
        birth_day = 0
    else:
        birth_day = (year_date - today).days
    return birth_day

def get_ciba():
    url = "http://open.iciba.com/dsapi/"
    try:
        r = get(url, timeout=15)
        note_en = r.json()["content"]
        note_ch = r.json()["note"]
        return note_ch, note_en
    except Exception as e:
        print(f"[WARN] 获取每日一句失败: {e}")
        return "生命中最重要的就是爱。", "The most important thing in life is to love."

def send_message(to_user, access_token, region_name, weather, temp, max_temp, min_temp, wind_dir, tips, note_ch, note_en, my_horoscope, her_horoscope):
    url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"
    week_list = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"]
    
    now = datetime.now()
    today = now.date()
    week = week_list[today.isoweekday() % 7]
    
    love_date_str = config.get("love_date")
    love_days = "未知"
    if love_date_str:
        love_date_obj = datetime.strptime(love_date_str, "%Y-%m-%d").date()
        days = (today - love_date_obj).days
        if days >= 0:
            love_days = f"第{days}天"
        else:
            love_days = f"还有{abs(days)}天才在一起哦"

    birthdays = {}
    for k, v in config.items():
        if k.startswith("birthday"):
            birthdays[k] = v

    data = {
        "touser": to_user,
        "template_id": config.get("template_id") or os.environ.get("TEMPLATE_ID"),
        "url": "http://weixin.qq.com/download",
        "topcolor": "#FF0000",
        "data": {
            "date": {"value": f"{today} {week}", "color": get_color()},
            "region": {"value": region_name, "color": get_color()},
            "weather": {"value": weather, "color": get_color()},
            "temp": {"value": temp, "color": get_color()},
            "max_temp": {"value": max_temp, "color": get_color()},
            "min_temp": {"value": min_temp, "color": get_color()},
            "wind_dir": {"value": wind_dir, "color": get_color()},
            "tips": {"value": tips, "color": get_color()},
            "love_day": {"value": love_days, "color": get_color()},
            "note_en": {"value": note_en, "color": get_color()},
            "note_ch": {"value": note_ch, "color": get_color()},
            "my_horoscope": {"value": my_horoscope, "color": get_color()},
            "her_horoscope": {"value": her_horoscope, "color": get_color()}
        }
    }

    for key, value in birthdays.items():
        birth_day = get_birthday(value["birthday"], today.year, today)
        if birth_day == 0:
            birthday_data = f"今天 {value['name']} 生日哦，祝生日快乐！🎂"
        else:
            birthday_data = f"距离 {value['name']} 的生日还有 {birth_day} 天"
        data["data"][key] = {"value": birthday_data, "color": get_color()}

    headers = {'Content-Type': 'application/json'}
    try:
        response = post(url, headers=headers, json=data, timeout=15).json()
        if response.get("errcode") == 0:
            print(f"[OK] 推送给用户 {to_user} 成功")
            return True
        else:
            print(f"[FAIL] 推送给用户 {to_user} 失败: errcode={response.get('errcode')}, errmsg={response.get('errmsg')}")
            return False
    except Exception as e:
        print(f"[FAIL] 推送给用户 {to_user} 异常: {e}")
        return False

def load_config():
    """
    加载配置，优先级：config.json > config.txt > 环境变量
    环境变量用于 GitHub Actions 等无配置文件场景
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    config_txt_path = os.path.join(script_dir, "config.txt")
    
    # 1. 优先读 config.json
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # 2. 其次读 config.txt
    if os.path.exists(config_txt_path):
        print("正在从 config.txt 加载配置")
        with open(config_txt_path, "r", encoding="utf-8") as f:
            lines = [line.split("#")[0].strip() for line in f.readlines()]
            content = "".join(lines)
            try:
                return json.loads(content)
            except:
                return eval(content)
    
    # 3. 从环境变量构建配置（GitHub Actions 场景）
    print("未找到配置文件，从环境变量加载配置")
    cfg = {
        "app_id": os.environ.get("APP_ID"),
        "app_secret": os.environ.get("APP_SECRET"),
        "template_id": os.environ.get("TEMPLATE_ID"),
        "user": os.environ.get("USER", "").split(",") if os.environ.get("USER") else [],
        "weather_key": os.environ.get("WEATHER_KEY", ""),
        "region": os.environ.get("REGION", "北京"),
        "my_constellation": os.environ.get("MY_CONSTELLATION", "狮子座"),
        "her_constellation": os.environ.get("HER_CONSTELLATION", "双鱼座"),
        "love_date": os.environ.get("LOVE_DATE", ""),
        "note_ch": os.environ.get("NOTE_CH", ""),
        "note_en": os.environ.get("NOTE_EN", ""),
    }
    
    # 生日配置：从环境变量读取（格式：BIRTHDAY_ME=杨伟博,2002-07-28）
    birthday_me = os.environ.get("BIRTHDAY_ME", "")
    if birthday_me:
        parts = birthday_me.split(",")
        if len(parts) == 2:
            cfg["birthday_me"] = {"name": parts[0].strip(), "birthday": parts[1].strip()}
    
    birthday_her = os.environ.get("BIRTHDAY_HER", "")
    if birthday_her:
        parts = birthday_her.split(",")
        if len(parts) == 2:
            cfg["birthday_her"] = {"name": parts[0].strip(), "birthday": parts[1].strip()}
    
    return cfg


if __name__ == "__main__":
    config = load_config()

    accessToken = get_access_token()
    
    users = config.get("user") or (os.environ.get("USER").split(",") if os.environ.get("USER") else [])
    if not users:
        print("未配置接收用户")
        sys.exit(1)

    region = config.get("region") or os.environ.get("REGION") or "北京"
    weather, temp, max_temp, min_temp, wind_dir, tips, region_name = get_weather(region)
    
    note_ch = config.get("note_ch")
    note_en = config.get("note_en")
    if not note_ch or not note_en:
        note_ch, note_en = get_ciba()
    
    my_constellation = config.get("my_constellation") or "狮子座"
    her_constellation = config.get("her_constellation") or "双鱼座"
    my_horoscope = get_horoscope(my_constellation)
    her_horoscope = get_horoscope(her_constellation)

    success_count = 0
    fail_count = 0
    for user in users:
        ok = send_message(user, accessToken, region_name, weather, temp, max_temp, min_temp, wind_dir, tips, note_ch, note_en, my_horoscope, her_horoscope)
        if ok:
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\n[汇总] 成功 {success_count} 人，失败 {fail_count} 人")
    if fail_count > 0:
        sys.exit(1)
