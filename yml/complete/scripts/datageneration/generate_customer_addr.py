from faker import Faker
import random
import time
from datetime import datetime

# {
#     "customer_addr_id": 1106,
#     "zip": "100002",
#     "province": "广东省",
#     "city": "广州市",
#     "district": "天河区",
#     "address": "天河北路100号",
#     "is_default": 1,
#     "event_time": "2025-02-05T13:00:00.000Z",
#     "customer_id": 50003
# }

def return_customer_addr(database_type):
    fake = Faker(locale='zh_CN')

    # 邮编
    postcode = fake.postcode()

    # 省份
    province = fake.province()

    # 城市
    city = fake.city()

    # 地区
    district = fake.district()

    # 具体地址
    address = fake.address()

    # 是够默认
    is_default_list = [1, 0]
    is_default = random.choice(is_default_list)

    customer_addr = (postcode, province, city, district, address, is_default)
    if database_type == 'mysql':
        return customer_addr
    else:
        # 获取当前时间戳
        timestamp = time.time()
        # 将时间戳转换为整数
        id = int(timestamp)

        # 创建一个 datetime 对象
        now = datetime.now()

        # 转换为字符串
        str_now = now.strftime("%Y-%m-%d %H:%M:%S")

        customer_addr = (id, postcode, province, city, district, address, is_default, str_now)
        return customer_addr

