import streamlit as st
import pandas as pd
import datetime
import io

# Настройка страницы WMS
st.set_page_config(page_title="WMS Ручной Период Биллинга", layout="wide", page_icon="🌐")

st.title("📐 WMS Фулфилмент: Настройка произвольного периода биллинга")
st.write(f"Текущее время системы: `{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`")

# --- ИНИЦИАЛИЗАЦИЯ ДИНАМИЧЕСКОЙ БАЗЫ ТОВАРОВ И ИСТОРИИ ---
if 'wms_inventory' not in st.session_state:
    st.session_state.wms_inventory = {
        'Коробка Обувная XL': {
            'length_cm': 30.0, 'width_cm': 20.0, 'height_cm': 15.0,
            'boxes': 5, 'pcs_in_box': 20, 'physical_stock': 100, 'fbs_limit': 20
        },
        'Чехол iPhone 15': {
            'length_cm': 15.0, 'width_cm': 8.0, 'height_cm': 1.5,
            'boxes': 2, 'pcs_in_box': 50, 'physical_stock': 100, 'fbs_limit': 30
        }
    }

# Исторический лог заказов для проверки ручного фильтра дат
today_date = datetime.date.today()
if 'wms_history_orders' not in st.session_state:
    st.session_state.wms_history_orders = [
        {"Дата": today_date, "Источник": "Wildberries", "№ Заказа": "WB-9901", "SKU": "Коробка Обувная XL"},
        {"Дата": today_date, "Источник": "Ozon", "№ Заказа": "OZ-5502", "SKU": "Коробка Обувная XL"},
        {"Дата": today_date - datetime.timedelta(days=2), "Источник": "Wildberries", "№ Заказа": "WB-9811", "SKU": "Чехол iPhone 15"},
        {"Дата": today_date - datetime.timedelta(days=4), "Источник": "Ozon", "№ Заказа": "OZ-5412", "SKU": "Коробка Обувная XL"},
        {"Дата": today_date - datetime.timedelta(days=12), "Источник": "МойСклад", "№ Заказа": "МС-1024", "SKU": "Чехол iPhone 15"},
        {"Дата": today_date - datetime.timedelta(days=18), "Источник": "Wildberries", "№ Заказа": "WB-9100", "SKU": "Коробка Обувная XL"},
        {"Дата": today_date - datetime.timedelta(days=45), "Источник": "Ozon", "№ Заказа": "OZ-4100", "SKU": "Чехол iPhone 15"},
    ]

# --- БОКОВАЯ ПАНЕЛЬ: ТАРИФЫ И ПОЛНОСТЬЮ РУЧНОЙ ВЫБОР ДАТ ---
st.sidebar.header("⚙️ Тарифы 3PL-Биллинга")
m3_rate = st.sidebar.number_input("Хранение: 1 м³ / сутки (₽):", min_value=0.0, value=50.0, step=1.0)
fbs_processing_rate = st.sidebar.number_input("Сборка: 1 заказ FBS (₽):", min_value=0.0, value=35.0, step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("📅 Выбор произвольного периода")

# Интерактивный календарь для полностью ручного выбора диапазона (Начало и Конец периода)
# Пользователь кликает на дату начала, затем на дату окончания периода
custom_range = st.sidebar.date_input(
    "Укажите диапазон дат (с и по):", 
    value=(today_date - datetime.timedelta(days=6), today_date), # По умолчанию открываем за последнюю неделю
    max_value=today_date,
    help="Кликните на календарь. Первый клик — дата начала отчета, второй клик — дата окончания отчета."
)

# Выравниваем и валидируем даты ручного периода
if isinstance(custom_range, tuple) and len(custom_range) == 2:
    start_period, end_period = custom_range
else:
    start_period = custom_range if isinstance(custom_range, (list, tuple)) else custom_range
    end_period = start_period

# Считаем точное количество дней в выбранном вами вручную периоде
days_in_period = (end_period - start_period).days + 1

st.sidebar.markdown("---")
st.sidebar.success(f"📆 **Период установлен:**\n**С {start_period.strftime('%d.%m.%Y')}\nПо {end_period.strftime('%d.%m.%Y')}**\nКоличество дней для хранения: **{days_in_period}**")

# --- БЛОК 1: ПОАРТИКУЛЬНАЯ ПРИЕМКА ТОВАРА (КОРОБА И ШТУКИ) ---
st.subheader("📥 Модуль поартикульной приемки груза")
col_adm1, col_adm2 = st.columns(2)

with col_adm1:
    st.markdown("**1. Новое поступление (Приходная накладная)**")
    existing_skus = list(st.session_state.wms_inventory.keys())
    selected_sku = st.selectbox("Выберите артикул для приемки:", existing_skus + ["+ Создать новый артикул"])
    
    if selected_sku == "+ Создать новый артикул":
        target_sku = st.text_input("Введите название нового артикула (SKU):", value="Новый Товар SKU-100")
        c_l = st.number_input("Длина упаковки (см):", min_value=0.1, value=20.0)
        c_w = st.number_input("Ширина упаковки (см):", min_value=0.1, value=15.0)
        c_h = st.number_input("Высота упаковки (см):", min_value=0.1, value=10.0)
    else:
        target_sku = selected_sku
        c_l = st.session_state.wms_inventory[selected_sku]['length_cm']
        c_w = st.session_state.wms_inventory[selected_sku]['width_cm']
        c_h = st.session_state.wms_inventory[selected_sku]['height_cm']

with col_adm2:
    st.markdown("**2. Подсчет количества (Короба × Вложение)**")
    input_boxes = st.number_input("Количество принятых коробов (шт):", min_value=0, value=0, step=1)
    input_pcs_in_box = st.number_input("Количество штук внутри короба (вложение):", min_value=1, value=20, step=1)
    
    calculated_total_pcs = input_boxes * input_pcs_in_box
    st.info(f"📐 Будет зачислено на баланс: **{calculated_total_pcs} шт.**")
    
    if st.button("📦 Утвердить акт приемки", use_container_width=True):
        if calculated_total_pcs > 0:
            if target_sku not in st.session_state.wms_inventory:
                st.session_state.wms_inventory[target_sku] = {
                    'length_cm': c_l, 'width_cm': c_w, 'height_cm': c_h,
                    'boxes': input_boxes, 'pcs_in_box': input_pcs_in_box,
                    'physical_stock': calculated_total_pcs, 'fbs_limit': 0
                }
            else:
                st.session_state.wms_inventory[target_sku]['boxes'] += input_boxes
                st.session_state.wms_inventory[target_sku]['physical_stock'] += calculated_total_pcs
                
            st.success(f"Артикул '{target_sku}' успешно принят на баланс.")
            st.rerun()

# --- БЛОК 2: ТАБЛИЦА ТЕКУЩИХ ОСТАТКОВ СКЛАДА ---
st.markdown("---")
st.subheader("📊 Текущие остатки товаров на полках фулфилмента")

rows_stocks = []
total_warehouse_m3 = 0.0

for sku, data in st.session_state.wms_inventory.items():
    phys_stock = data['physical_stock']
    unit_m3 = (data['length_cm'] * data['width_cm'] * data['height_cm']) / 1000000
    total_sku_m3 = unit_m3 * phys_stock
    total_warehouse_m3 += total_sku_m3
    
    rows_stocks.append({
        "Артикул (SKU)": sku,
        "Габариты упаковки": f"{data['length_cm']}x{data['width_cm']}x{data['height_cm']} см",
        "Принято коробов (шт)": data['boxes'],
        "Вложение в короб": data['pcs_in_box'],
        "📦 НА ПОЛКАХ (шт)": phys_stock,
        "Занято объема (м³)": total_sku_m3
    })

if rows_stocks:
    st.dataframe(pd.DataFrame(rows_stocks), use_container_width=True, hide_index=True)
else:
    st.info("Склад пуст. Проведите первую приемку.")

# --- БЛОК 3: ЖУРНАЛ ЗАКАЗОВ FBS С ФИЛЬТРАЦИЕЙ ПО ВАШЕМУ РУЧНОМУ ПЕРИОДУ ---
st.markdown("---")
st.subheader(f"📋 Операционный журнал заказов FBS за произвольный период")

df_all_orders = pd.DataFrame(st.session_state.wms_history_orders)
# Фильтрация строго в рамках ручного диапазона дат [start_period, end_period]
df_filtered_orders = df_all_orders[(df_all_orders['Дата'] >= start_period) & (df_all_orders['Дата'] <= end_period)]
orders_count_in_period = len(df_filtered_orders)

# Выгрузка отфильтрованного ручного отчета в Excel
if not df_filtered_orders.empty:
    df_excel = df_filtered_orders.copy()
    df_excel['Дата'] = df_excel['Дата'].apply(lambda x: x.strftime('%Y-%m-%d'))
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Отчет FBS ручной')
    
    st.download_button(
        label=f"📥 Скачать отчет в Excel за выбранный период ({start_period.strftime('%d.%m')} - {end_period.strftime('%d.%m')})",
        data=buffer.getvalue(),
        file_name=f"fbs_custom_report_{start_period}_to_{end_period}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    st.dataframe(df_excel, use_container_width=True, hide_index=True)
else:
    st.write("🔒 За указанный диапазон дат заказов FBS в системе не обнаружено.")

# --- БЛОК 4: ИТОГОВЫЙ СВОДНЫЙ СЧЕТ (3PL-БИЛЛИНГ ЗА ЛЮБОЙ СРОК) ---
st.markdown("---")
st.subheader(f"🧾 Сводный 3PL-счет за период: с {start_period.strftime('%d.%m.%Y')} по {end_period.strftime('%d.%m.%Y')}")

# Математический накопительный расчет под произвольное число дней (days_in_period)
total_storage_cost_period = total_warehouse_m3 * m3_rate * days_in_period
total_processing_cost_period = orders_count_in_period * fbs_processing_rate
grand_total_period = total_storage_cost_period + total_processing_cost_period

billing_period_data = [
    {
        "Услуга фулфилмента": "Ответственное хранение объема груза на полках (Накопительное за выбранный срок)",
        "База расчета": f"{total_warehouse_m3:.4f} м³ × {days_in_period} дн.",
        "Тарифная ставка": f"{m3_rate:.2f} ₽ за 1 м³ / сутки",
        "Итого к списанию за период": f"{total_storage_cost_period:.2f} ₽"
    },
    {
        "Услуга фулфилмента": "Сборка, упаковка и маркировка мультиканальных заказов FBS",
        "База расчета": f"{orders_count_in_period} шт. обработано за выбранный срок",
        "Тарифная ставка": f"{fbs_processing_rate:.2f} ₽ за 1 заказ",
        "Итого к списанию за период": f"{total_processing_cost_period:.2f} ₽"
    }
]

st.table(pd.DataFrame(billing_period_data))

# Финальный финансовый вердикт под кастомные даты
st.success(f"💰 **ИТОГО К СПИСАНИЮ С БАЛАНСА СЕЛЛЕРА ЗА ВЫБРАННЫЙ ПЕРИОД ({days_in_period} дн.):** **{grand_total_period:.2f} ₽**")
