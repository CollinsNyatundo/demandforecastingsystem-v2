import sys
sys.path.append('app-ui')
from api_client import send_prediction
print(send_prediction({"temp": 0.5, "humidity": 0.65, "wind_speed": 0.15, "hour": 14, "day_of_week": 3, "month": 6}))
