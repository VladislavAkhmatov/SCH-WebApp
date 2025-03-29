import requests

url = "https://70df-213-232-244-22.ngrok-free.app/generate-token.php"
data = {"login": "87081756417"}
headers = {"Content-Type": "application/json"}

response = requests.post(url, json=data, headers=headers)

print(response.status_code)  # Код ответа (200 — успех, 400/500 — ошибка)
print(response.text)  # Ответ сервера
