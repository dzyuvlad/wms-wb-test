import streamlit as st
import pandas as pd
import datetime

# Настройка страницы
st.set_page_config(page_title="WMS WB Тест | Единый Сток и Биллинг", layout="wide", page_icon="📦")

st.title("📐 Тестовая WMS: 1 Продавец ➔ Склад ➔ Wildberries")
st.write(f"Статус облачной синхронизации: Активен | `{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`")

# --- БОКОВАЯ ПАНЕЛЬ: ТАРИФЫ ---
st.sidebar.header("⚙️ Управление 3PL-Биллингом")
m3_rate = st.sidebar.number_input(
    "Тариф за 1 м³ в сутки (₽):", 
    min_value=0.0, 
    value=45.0, 
    step=1.0,
    help="Эта ставка умножается на объем товара на складе"
)

st.sidebar.markdown("---")
st.sidebar.info("📊 Тестовый контур: Данные подтягиваются напрямую из вашей Google Таблицы в режиме реального времени.")

# --- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ---
try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl="5s")
    
    if df.empty or 'seller_name' not in df.columns:
        st.error("Google Таблица пустая или структура столбцов неверна! Проверьте шапку таблицы.")
        st.stop()
        
    # --- МАТЕМАТИЧЕСКИЕ РАСЧЕТЫ КУБАТУРЫ И СТОКА ---
    df['Объем 1 шт (м³)'] = (df['length_cm'] * df['width_cm'] * df['height_cm']) / 1000000
    df['Общий объем на складе (м³)'] = df['Объем 1 шт (м³)'] * df['physical_stock']
    df['Единый Сток (Свободно)'] = df['physical_stock'] - df['fbs_reserve']
    df['Стоимость хранения/сутки (₽)'] = df['Общий объем на складе (м³)'] * m3_rate

    # --- ОТОБРАЖЕНИЕ АНАЛИТИКИ НА ЭКРАНЕ ---
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Общий объем товаров (м³)", f"{df['Общий объем на складе (м³)'].sum():.4f} м³")
    with c2:
        st.metric("Физический остаток на складе", f"{int(df['physical_stock'].sum())} шт")
    with c3:
        st.metric("Суточный биллинг за хранение", f"{df['Стоимость хранения/сутки (₽)'].sum():,.2f} ₽")

    st.markdown("---")

    st.subheader("🌐 Мониторинг Единого Стока: Wildberries")
    wb_view = df[['seller_name', 'sku', 'physical_stock', 'fbs_reserve', 'Единый Сток (Свободно)', 'stock_wb']].rename(columns={
        'seller_name': 'Продавец (Селлер)',
        'sku': 'Артикул товара (SKU)',
        'physical_stock': 'На складе (Физ. остаток)',
        'fbs_reserve': 'Резерв под заказы FBS',
        'stock_wb': 'Выставленный сток на WB по API'
    })
    st.dataframe(wb_view, use_container_width=True, hide_index=True)

    st.markdown("---")

    st.subheader("💰 3PL-Биллинг: Расчет по габаритам (М³)")
    billing_view = df[['seller_name', 'sku', 'length_cm', 'width_cm', 'height_cm', 'physical_stock', 'Общий объем на складе (м³)', 'Стоимость хранения/сутки (₽)']].rename(columns={
        'seller_name': 'Продавец', 'sku': 'Артикул', 'length_cm': 'Длина (см)', 'width_cm': 'Ширина (см)', 'height_cm': 'Высота (см)', 'physical_stock': 'Остаток (шт)'
    })
    st.dataframe(billing_view.style.format({'Общий объем на складе (м³)': '{:.4f}', 'Стоимость хранения/сутки (₽)': '{:.2f} ₽'}), use_container_width=True, hide_index=True)

    st.subheader("🧾 Сводный счет на оплату за текущие сутки")
    summary = df.groupby('seller_name').agg({'Общий объем на складе (м³)': 'sum', 'Стоимость хранения/сутки (₽)': 'sum'}).reset_index().rename(columns={
        'seller_name': 'Наименование юридического лица', 'Общий объем на складе (м³)': 'Итого занято объема (м³)', 'Стоимость хранения/сутки (₽)': 'Сумма к списанию за 24 часа'
    })
    st.table(summary.style.format({'Итого занято объема (м³)': '{:.4f}', 'Сумма к списанию за 24 часа': '{:.2f} ₽'}))

except Exception as e:
    st.warning("⚙️ Система готова к работе и ожидает подключения к базе данных.")
    st.info("Чтобы таблицы отобразились, подключите вашу Google Таблицу в настройках 'Advanced Settings -> Secrets' на платформе Streamlit Cloud.")
