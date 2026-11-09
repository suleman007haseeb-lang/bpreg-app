"""
BytePlus registration endpoint - runs on Render.com (US IP).
GET /reg -> triggers registration, returns result JSON
"""
from flask import Flask, jsonify
import requests, re, time, random, string, json, os

app = Flask(__name__)
ARK_CN = "https://ark.cn-beijing.volces.com/api/v3"
MODEL = "doubao-seedance-2-5-260628"

def test_key(key):
    try:
        r = requests.post(f"{ARK_CN}/contents/generations/tasks",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": MODEL, "content": [{"type": "text", "text": "cat running"}]},
            timeout=14)
        ec = ""
        try: ec = r.json().get("error", {}).get("code", "")
        except: pass
        return r.status_code, ec
    except Exception as e:
        return 0, str(e)

@app.route("/")
def index():
    return jsonify({"status": "alive", "service": "byteplus-reg"})

@app.route("/ip")
def show_ip():
    try:
        ip_info = requests.get("https://ipinfo.io/json", timeout=10).json()
        S = requests.Session()
        S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        S.headers["Accept"] = "text/html"
        S.get("https://console.byteplus.com/auth/signup", timeout=12)
        spti = S.cookies.get("__spti", "")
        return jsonify({
            "ip": ip_info.get("ip"),
            "org": ip_info.get("org"),
            "country": ip_info.get("country"),
            "spti": spti,
            "flagged": "bapxu9rXuEQMtPL" in spti
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/reg")
def register():
    result = {"step": "init"}
    
    # IP check
    try:
        ip_info = requests.get("https://ipinfo.io/json", timeout=10).json()
        result["ip"] = ip_info.get("ip")
        result["org"] = ip_info.get("org")
        result["country"] = ip_info.get("country")
    except: pass
    
    USERNAME = "bpdev" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    PASSWORD = "BpP1us!2026#A"
    H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
    
    # Get temp email
    try:
        gm = requests.get("https://api.guerrillamail.com/ajax.php?f=get_email_address",
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        _user = gm.get("email_addr", "").split("@")[0]
        sid = gm.get("sid_token", "")
        requests.get("https://api.guerrillamail.com/ajax.php",
                     params={"f": "set_email_user", "email_user": _user, "lang": "en",
                             "sid_token": sid, "in": "guerrillamail.com"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        email = f"{_user}@guerrillamail.com"
        result["email"] = email
    except Exception as e:
        return jsonify({"error": f"email: {e}"})
    
    # Setup byteplus session
    S = requests.Session()
    S.headers.update({**H, "Accept": "text/html"})
    r0 = S.get("https://console.byteplus.com/auth/signup", timeout=15)
    spti = S.cookies.get("__spti", "")
    result["spti"] = spti
    result["flagged"] = "bapxu9rXuEQMtPL" in spti
    
    S.headers.update({
        "Accept": "application/json",
        "Origin": "https://console.byteplus.com",
        "Referer": "https://console.byteplus.com/auth/signup",
        "X-Csrf-Token": "8b13c7ddf17a645320fff792b453c01c",
    })
    
    # Send OTP
    r_otp = S.post("https://console.byteplus.com/api/passport/login/sendSignupEmailforBP",
                   json={"Email": email, "AccountType": "byteplus"}, timeout=15)
    otp_ec = ""
    try: otp_ec = r_otp.json().get("ResponseMetadata", {}).get("Error", {}).get("Code", "")
    except: pass
    result["otp_send"] = {"status": r_otp.status_code, "ec": otp_ec}
    
    if r_otp.status_code != 200 or otp_ec:
        result["error"] = f"OTP send failed: {r_otp.text[:200]}"
        return jsonify(result)
    
    result["step"] = "waiting_otp"
    
    # Wait for OTP
    otp = None
    for i in range(40):
        time.sleep(3)
        try:
            gm2 = requests.get(f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={sid}",
                               headers={"User-Agent": "Mozilla/5.0"}, timeout=15).json()
            for mail in gm2.get("list", []):
                subj = mail.get("mail_subject", "")
                if any(x in subj.lower() for x in ["byteplus", "verify", "code", "one-time"]):
                    mid = mail.get("mail_id")
                    br = requests.get(f"https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id={mid}&sid_token={sid}",
                                      headers={"User-Agent": "Mozilla/5.0"}, timeout=15).json()
                    body = br.get("mail_body", "") + br.get("mail_body_html", "")
                    codes = re.findall(r'\b(\d{6})\b', re.sub(r'<[^>]+>', ' ', body))
                    if codes:
                        otp = codes[0]
                        break
        except: pass
        if otp:
            break
    
    if not otp:
        result["error"] = "No OTP received"
        return jsonify(result)
    
    result["otp"] = otp
    result["step"] = "registering"
    
    # Register
    r_reg = S.post("https://console.byteplus.com/api/passport/login/signup",
                   json={"Email": email, "AccountName": USERNAME, "Password": PASSWORD,
                         "VerificationCode": otp, "AccountType": "byteplus",
                         "AcceptAgreements": ["byteplus_terms", "byteplus_privacy"]},
                   timeout=15)
    reg_ec = ""
    try: reg_ec = r_reg.json().get("ResponseMetadata", {}).get("Error", {}).get("Code", "")
    except: pass
    result["register"] = {"status": r_reg.status_code, "ec": reg_ec, "body": r_reg.text[:400]}
    
    if r_reg.status_code == 200 and not reg_ec:
        result["SUCCESS"] = True
        result["credentials"] = {"email": email, "username": USERNAME, "password": PASSWORD}
        result["step"] = "success"
    else:
        result["step"] = "failed"
    
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
