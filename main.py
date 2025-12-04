import os
from dotenv import load_dotenv

from aliexpress_api import AliexpressApi, models

# تحميل متغيرات البيئة
load_dotenv()

KEY = os.environ.get("KEY")
SECRET = os.environ.get("SECRET")
TRACKING_ID = os.environ.get("TRACKING_ID")

# إنشاء كائن API
aliexpress = AliexpressApi(
    KEY,
    SECRET,
    models.Language.EN,
    models.Currency.USD,
    TRACKING_ID
)

# طباعة جميع الدوال والخصائص داخل aliexpress
print("\n========================")
print("AVAILABLE METHODS INSIDE aliexpress:")
print("========================\n")

for m in dir(aliexpress):
    print(m)

print("\n========== END ==========\n")
