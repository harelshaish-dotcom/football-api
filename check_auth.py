import requests

BASE = "http://127.0.0.1:8000"
EMAIL = "harelshaish@gmail.com"
PASSWORD = "examplepass"

# 1. Login returns a token
r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
print("1. login:", r.status_code, r.text[:80])
token = r.json().get("access_token")

# 2. Protected route rejects requests with no token
r = requests.get(f"{BASE}/users/me")
print("2. /users/me without token:", r.status_code, r.text)

# 3. Protected route accepts the token
headers = {"Authorization": f"Bearer {token}"}
r = requests.get(f"{BASE}/users/me", headers=headers)
print("3. /users/me with token:", r.status_code, r.text)

# 4. The user in the database is an admin
if r.status_code == 200:
    print("4. is_admin:", r.json().get("is_admin"))