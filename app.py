import streamlit as st
import pandas as pd
import datetime
import requests
import io
from dateutil import parser

st.set_page_config(page_title="WMS Ручной Сток | Единый Баланс", layout="wide", page_icon="🌐")

st.title("🌐 WMS Фулфилмент: Ручной лимит FBS + Мультиканальный Единый Сток")
st.write(f"Последняя синхронизация всех API: `{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`")

if 'wms_initial_acceptance' not in st.session_state:
    st.session_state.wms_initial_acceptance = 100  
if 'wms_manual_fbs_limit' not in st.session_state:
    st.session_state.wms_manual_fbs_limit = 20     

sku_name = "Коробка Обувная XL"
l, w, h = 30.0, 20.0, 15.0

st.sidebar.header("🔑 Подключение каналов API")
wb_token = st.sidebar.text_input("API Токен WB:", type="password", key="wb")
ozon_client_id = st.sidebar.text_input("Ozon Client-ID:", key="ozon_id")
ozon_api_key = st.sidebar.text_input("Ozon API Key:", type="password", key="ozon_key")
ms_token = st.sidebar.text_input("API Токен МойСклад:", type="password", key="ms")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Тарифы 3PL-Биллинга")
m3_rate = st.sidebar.number_input("Хранение: 1 м³ / сутки (₽):", min_value=0.0, value=50.0, step=1.0)
fbs_processing_rate = st.sidebar.number_input("Сборка: 1 заказ FBS (₽):", min_value=0.0, value=35.0, step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("📅 Фильтр отчетов")
today = datetime.date.today()
start_of_month = today.replace(day=1)
date_range = st.sidebar.date_input("Выберите период:", value=(start_of_month, today), max_value=today)

st.subheader("📥 Модуль оперативного учета склада")
col_adm1, col_adm2 = st.columns(2)

with col_adm1:
    st.markdown("**1. Поступление / Приемка товара**")
    new_accept = st.number_input("Принять товар от селлера на баланс (шт):", min_value=0, value=0, step=10)
    if st.button("📦 Зафиксировать поступление", use_container_width=True):
        st.session_state.wms_initial_acceptance += new_accept
        st.success(f"Товар принят! Баланс на полках увеличен на +{new_accept} шт.")
        st.rerun()

with col_adm2:
    st.markdown("**2. Управление лимитом продаж FBS (ВРУЧНУЮ)**")
    manual_input_fbs = st.number_input("Задать текущий доступный лимит FBS (шт):", min_value=0, value=int(st.session_state.wms_manual_fbs_limit), step=1)
    if st.button("🔄 Выставить лимит на WB, Ozon, МойСклад", use_container_width=True):
        st.session_state.wms_manual_fbs_limit = manual_input_fbs
        st.success(f"Новый лимит в {manual_input_fbs} шт. зафиксирован и подготовлен к отправке по API.")
        st.rerun()

api_fbo_orders_count = 0
all_fbs_orders_list = []
is_live_mode = wb_token and ozon_client_id and ozon_api_key and ms_token

if is_live_mode:
    with st.spinner("🤖 Робот проверяет новые заказы через API..."):
        try:
            wb_headers = {"Authorization": wb_token, "Content-Type": "application/json"}
            wb_res = requests.get("https://wildberries.ru", headers=wb_headers, timeout=4)
            if wb_res.status_code == 200:
                for o in wb_res.json().get('orders', []):
                    all_fbs_orders_list.append({"Источник": "Wildberries", "№ Заказа": o.get('id'), "Дата": parser.isoparse(o.get('createdAt')).date(), "SKU": sku_name, "Тариф сборки": fbs_processing_rate})
            ozon_headers = {"Client-Id": ozon_client_id, "Api-Key": ozon_api_key, "Content-Type": "application/json"}
            ozon_body = {"dir": "asc", "filter": {"status": "awaiting_packaging"}, "limit": 50, "with": {}}
            ozon_res = requests.post("https://ozon.ru", headers=ozon_headers, json=ozon_body, timeout=4)
            if ozon_res.status_code == 200:
                for p in ozon_res.json().get('result', {}).get('postings', []):
                    all_fbs_orders_list.append({"Источник": "Ozon", "№ Заказа": p.get('posting_number'), "Дата": parser.isoparse(p.get('in_process_at')).date(), "SKU": sku_name, "Тариф сборки": fbs_processing_rate})
            ms_headers = {"Authorization": f"Bearer {ms_token}"} if ":" not in ms_token else None
            auth = tuple(ms_token.split(":")) if ":" in ms_token else None
            ms_res = requests.get("https://moysklad.ru", headers=ms_headers, auth=auth, timeout=4)
            if ms_res.status_code == 200:
                for order in ms_res.json().get('rows', []):
                    if order.get('state', {}).get('meta', {}).get('name') == "Новый":
                        all_fbs_orders_list.append({"Источник": "МойСклад", "№ Заказа": order.get('name'), "Дата": parser.isoparse(order.get('moment')).date(), "SKU": sku_name, "Тариф сборки": fbs_processing_rate})
        except Exception as e:
            st.sidebar.error(f"Ошибка API: {e}")
else:
    st.warning("🔑 Демо-режим. Пропишите API-ключи слева для работы с реальными личными кабинетами.")
    for i in range(1, 4):  
        all_fbs_orders_list.append({"Источник": "Wildberries", "№ Заказа": f"WB-77321{i}", "Дата": today, "SKU": sku_name, "Тариф сборки": fbs_processing_rate})
    for i in range(1, 3):  
        all_fbs_orders_list.append({"Источник": "Ozon", "№ Заказа": f"OZ-99432{i}", "Дата": today, "SKU": sku_name, "Тариф сборки": fbs_processing_rate})
    all_fbs_orders_list.append({"Источник": "МойСклад", "№ Заказа": f"МС-00043", "Дата": today, "SKU": sku_name, "Тариф сборки": fbs_processing_rate})
    api_fbo_orders_count = 10  

allocated_to_fbo_total = 20  
total_fbs_all_channels = len(all_fbs_orders_list)

my_warehouse_physical = st.session_state.wms_initial_acceptance - allocated_to_fbo_total - total_fbs_all_channels
current_total_balance = st.session_state.wms_initial_acceptance - (api_fbo_orders_count + total_fbs_all_channels)
live_unified_stock_to_api = max(0, st.session_state.wms_manual_fbs_limit - total_fbs_all_channels)

df_all_orders = pd.DataFrame(all_fbs_orders_list)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    df_filtered = df_all_orders[(df_all_orders['Дата'] >= start_date) & (df_all_orders['Дата'] <= end_date)]
else:
    start_date = date_range if isinstance(date_range, (list, tuple)) else date_range
    df_filtered = df_all_orders[df_all_orders['Дата'] == start_date]
    end_date = start_date

filtered_orders_count = len(df_filtered)

item_m3 = (l * w * h) / 1000000
total_m3_active = item_m3 * my_warehouse_physical
billing_storage = total_m3_active * m3_rate
billing_processing = filtered_orders_count * fbs_processing_rate
grand_total = billing_storage + billing_processing

st.markdown("---")
st.subheader("📊 Мониторинг Мультиканального Единого Стока")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("📦 НА ВАШИХ ПОЛКАХ (ФИЗ)", f"{my_warehouse_physical} шт")
with c2:
    st.metric("🔄 ЕДИНЫЙ СТОК НА ВИТРИНАХ", f"{live_unified_stock_to_api} шт")
with c3:
    st.metric("Платный объем хранения (м³)", f"{total_m3_active:.4f} м³")
with c4:
    st.metric("Сквозной баланс селлера", f"{current_total_balance} шт")

channels_matrix = [{
    "Продавец": "ИП Иванов (Мультиканал)", "Артикул (SKU)": sku_name, "Физически у вас": my_warehouse_physical,
    "Выставлено руками под FBS": st.session_state.wms_manual_fbs_limit, "Текущий Сток на WB (API)": live_unified_stock_to_api,
    "Текущий Сток на Ozon (API)": live_unified_stock_to_api, "Текущий Сток в МойСклад (API)": live_unified_stock_to_api, "Уехало на FBO (WB + Ozon)": allocated_to_fbo_total
}]
st.dataframe(pd.DataFrame(channels_matrix), use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader(f"📋 Консолидированный журнал заказов (Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})")

df_excel = df_filtered.copy()
df_excel['Дата'] = df_excel['Дата'].apply(lambda x: x.strftime('%Y-%m-%d'))
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    df_excel.to_excel(writer, index=False, sheet_name='Мультиканал FBS')

st.download_button(
    label="📥 Скачать сводный мультиканальный отчет в Excel",
    data=buffer.getvalue(),
    file_name=f"multichannel_report_{start_date}_to_{end_date}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

st.dataframe(df_excel, use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("🧾 Сводный отчет по начислениям (Мультиканальный биллинг)")

billing_data = [
    {"Услуга фулфилмента": "Ответственное хранение (Платные кубометры на ваших полках)", "База расчета": f"{my_warehouse_physical} шт / {total_m3_active:.4f} м³", "Тарифная ставка": f"{m3_rate:.2f} ₽ за 1 м³ / сутки", "Итого (₽)": f"{billing_storage:.2f} ₽"},
    {"Услуга фулфилмента": f"Сборка и упаковка мультиканальных заказов FBS (За выбранный период)", "База расчета": f"{filtered_orders_count} шт зафиксировано (WB + Ozon + МойСклад)", "Тарифная ставка": f"{fbs_processing_rate:.2f} ₽ за 1 заказ", "Итого (₽)": f"{billing_processing:.2f} ₽"}
]
st.table(pd.DataFrame(billing_data))
st.info(f"💰 **ОБЩАЯ СУММА К СУТОЧНОМУ СПИСАНИЮ С БАЛАНСА КЛИЕНТА:** **{grand_total:.2f} ₽**")
