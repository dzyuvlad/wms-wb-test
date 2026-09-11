import streamlit as st
import pandas as pd
import datetime
import requests
import io

# Настройка страницы WMS
st.set_page_config(page_title="WMS Фулфилмент", layout="wide", page_icon="🌐")

st.title("📦 Профессиональная WMS: Система управления фулфилментом")
st.write(f"Последняя синхронизация базы данных: `{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`")

# --- ИНИЦИАЛИЗАЦИЯ ДИНАМИЧЕСКОЙ БАЗЫ ТОВАРОВ ---
if 'wms_inventory' not in st.session_state:
    st.session_state.wms_inventory = {}

if 'm3_rate' not in st.session_state:
    st.session_state.m3_rate = 50.0
if 'fbs_processing_rate' not in st.session_state:
    st.session_state.fbs_processing_rate = 35.0

# --- БАЗОВЫЙ КАЛЕНДАРЬ ПЕРИОДОВ ---
today_date = datetime.date.today()
if 'start_period' not in st.session_state:
    st.session_state.start_period = today_date - datetime.timedelta(days=6)
if 'end_period' not in st.session_state:
    st.session_state.end_period = today_date

# --- ФУНКЦИЯ АВТОМАТИЧЕСКОГО ИМПОРТА КАРТОЧЕК ИЗ API ---
def load_live_cards_from_api(wb_tok, oz_id, oz_key):
    live_data = {}
    
    # 1. Wildberries (API Контента)
    if wb_tok:
        wb_headers = {"Authorization": wb_tok, "Content-Type": "application/json"}
        wb_url = "https://wildberries.ru"
        wb_body = {"settings": {"cursor": {"limit": 50}, "filter": {"withPhoto": 1}}}
        try:
            res = requests.post(wb_url, headers=wb_headers, json=wb_body, timeout=5)
            if res.status_code == 200:
                cards = res.json().get('cards', [])
                for c in cards:
                    vendor_code = c.get('vendorCode', 'Не указан')
                    title = c.get('title', 'Товар WB')
                    
                    color = "Не указан"
                    for char in c.get('characteristics', []):
                        if char.get('name') == 'Цвет':
                            color = ", ".join(char.get('value', []))
                    
                    dimensions = c.get('dimensions', {})
                    length = float(dimensions.get('length', 20))
                    width = float(dimensions.get('width', 15))
                    height = float(dimensions.get('height', 10))
                    
                    media = c.get('mediaUrls', [])
                    img_url = media[0] if media else "https://icons8.com"
                    
                    for size in c.get('sizes', []):
                        for barcode in size.get('skus', []):
                            key = f"WB-{barcode}"
                            live_data[key] = {
                                'source': 'Wildberries', 'img': img_url, 'title': title,
                                'vendor_code': vendor_code, 'barcode': barcode, 'color': color,
                                'length_cm': length, 'width_cm': width, 'height_cm': height,
                                'boxes': 0, 'pcs_in_box': 1, 'physical_stock': 0, 'fbs_limit': 0
                            }
        except Exception:
            pass

    # 2. Ozon (API Поставщика)
    if oz_id and oz_key:
        oz_headers = {"Client-Id": oz_id, "Api-Key": oz_key, "Content-Type": "application/json"}
        try:
            res_list = requests.post("https://ozon.ru", headers=oz_headers, json={"limit": 50}, timeout=5)
            if res_list.status_code == 200:
                items = res_list.json().get('result', {}).get('items', [])
                product_ids = [i.get('product_id') for i in items]
                
                res_info = requests.post("https://ozon.ru", headers=oz_headers, json={"product_id": product_ids}, timeout=5)
                if res_info.status_code == 200:
                    products = res_info.json().get('result', {}).get('items', [])
                    for p in products:
                        vendor_code = p.get('offer_id', 'Не указан')
                        title = p.get('name', 'Товар Ozon')
                        barcode = p.get('barcode', 'Не указан')
                        img_url = p.get('primary_image', "https://icons8.com")
                        
                        length = float(p.get('depth', 200)) / 10 if p.get('depth', 200) > 100 else float(p.get('depth', 20))
                        width = float(p.get('width', 150)) / 10 if p.get('width', 150) > 100 else float(p.get('width', 15))
                        height = float(p.get('height', 100)) / 10 if p.get('height', 100) > 100 else float(p.get('height', 10))
                        
                        key = f"OZON-{barcode}"
                        live_data[key] = {
                            'source': 'Ozon', 'img': img_url, 'title': title,
                            'vendor_code': vendor_code, 'barcode': barcode, 'color': "См. в ЛК Ozon",
                            'length_cm': length, 'width_cm': width, 'height_cm': height,
                            'boxes': 0, 'pcs_in_box': 1, 'physical_stock': 0, 'fbs_limit': 0
                        }
        except Exception:
            pass
            
    return live_data

# Проверка сохраненных токенов
wb_token = st.session_state.get('wb_token_saved', '')
ozon_client_id = st.session_state.get('ozon_id_saved', '')
ozon_api_key = st.session_state.get('ozon_key_saved', '')

is_api_connected = wb_token or (ozon_client_id and ozon_api_key)

if is_api_connected:
    api_inventory = load_live_cards_from_api(wb_token, ozon_client_id, ozon_api_key)
    for k, v in api_inventory.items():
        if k not in st.session_state.wms_inventory:
            st.session_state.wms_inventory[k] = v
else:
    if not st.session_state.wms_inventory:
        st.session_state.wms_inventory = {
            'DEMO-1': {
                'source': 'Wildberries', 'img': 'https://wbstatic.net',
                'title': 'Кроссовки спортивные', 'vendor_code': 'KROSS-BLK-42', 'barcode': '4607123456711', 'color': 'Черный матовый',
                'length_cm': 32.0, 'width_cm': 21.0, 'height_cm': 12.0, 'boxes': 4, 'pcs_in_box': 12, 'physical_stock': 48, 'fbs_limit': 15
            },
            'DEMO-2': {
                'source': 'Ozon', 'img': 'https://ozoncontent.ru',
                'title': 'Чехол силиконовый', 'vendor_code': 'CASE-IPH15-CLR', 'barcode': '4607123456722', 'color': 'Прозрачный',
                'length_cm': 16.0, 'width_cm': 8.5, 'height_cm': 1.2, 'boxes': 2, 'pcs_in_box': 50, 'physical_stock': 100, 'fbs_limit': 40
            }
        }
# --- ПОДГОТОВКА ТАБЛИЦ ДО ОТРИСОВКИ ---
rows_stocks = []
total_warehouse_m3 = 0.0

for k, data in st.session_state.wms_inventory.items():
    phys_stock = data['physical_stock']
    unit_m3 = (data['length_cm'] * data['width_cm'] * data['height_cm']) / 1000000
    total_sku_m3 = unit_m3 * phys_stock
    total_warehouse_m3 += total_sku_m3
    
    rows_stocks.append({
        "Площадка": data['source'], "Фото": data['img'], "Название товара": data['title'],
        "Артикул продавца": data['vendor_code'], "Баркод (Штрихкод)": data['barcode'], "Цвет": data['color'],
        "Принято коробов": data['boxes'], "Шт в коробе": data['pcs_in_box'], "На полках (Физ, шт)": phys_stock,
        "Лимит FBS": data['fbs_limit'], "Объем (м³)": total_sku_m3, "Хранение / сутки": total_sku_m3 * st.session_state.m3_rate
    })

df_stocks_matrix = pd.DataFrame(rows_stocks)

# --- СОЗДАНИЕ ВКЛАДОК ---
tab_receive, tab_stocks, tab_billing, tab_api = st.tabs([
    "📥 Поартикульная Приемка", "📊 Текущие Остатки (Матрица)", "📅 Счета и 3PL-Биллинг", "🔑 Настройки API и Тарифы"
])

# ВКЛАДКА 1: ПРИЕМКА ТОВАРА
with tab_receive:
    st.subheader("📥 Регистрация прихода новой партии (Короба × Вложение)")
    sku_options = {f"[{v['source']}] {v['title']} ({v['vendor_code']})": k for k, v in st.session_state.wms_inventory.items()}
    
    col_rec1, col_rec2 = st.columns(2)
    with col_rec1:
        selected_option = st.selectbox("Выберите товар для приемки:", list(sku_options.keys()))
        db_key = sku_options[selected_option]
        st.write("---")
        st.image(st.session_state.wms_inventory[db_key]['img'], width=120)
        st.write(f"**Артикул:** `{st.session_state.wms_inventory[db_key]['vendor_code']}`")
        st.write(f"**Баркод:** `{st.session_state.wms_inventory[db_key]['barcode']}` | **Цвет:** `{st.session_state.wms_inventory[db_key]['color']}`")

    with col_rec2:
        input_boxes = st.number_input("Количество коробов (шт):", min_value=0, value=0, step=1, key="box_rec")
        input_pcs_in_box = st.number_input("Вложение в короб (шт):", min_value=1, value=st.session_state.wms_inventory[db_key]['pcs_in_box'], step=1, key="pcs_rec")
        calculated_total_pcs = input_boxes * input_pcs_in_box
        st.markdown(f"### 📐 Итого будет оприходовано: **{calculated_total_pcs} шт.**")
        
        if st.button("📦 Утвердить приходную накладную", use_container_width=True):
            if calculated_total_pcs > 0:
                st.session_state.wms_inventory[db_key]['boxes'] += input_boxes
                st.session_state.wms_inventory[db_key]['physical_stock'] += calculated_total_pcs
                st.session_state.wms_inventory[db_key]['pcs_in_box'] = input_pcs_in_box
                st.success(f"Зачислено {calculated_total_pcs} шт.")
                st.rerun()

# ВКЛАДКА 2: МАТРИЦА ОСТАТКОВ
with tab_stocks:
    st.subheader("📊 Мультиканальные остатки на складе фулфилмента")
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1: st.metric("Всего номенклатур (SKU)", len(df_stocks_matrix))
    with kpi2: st.metric("Физический остаток на полках", f"{int(df_stocks_matrix['На полках (Физ, шт)'].sum())} шт")
    with kpi3: st.metric("Общий объем товаров", f"{total_warehouse_m3:.4f} м³")
        
    st.write("---")
    st.data_editor(
        df_stocks_matrix[["Площадка", "Фото", "Название товара", "Артикул продавца", "Баркод (Штрихкод)", "Цвет", "Принято коробов", "Шт в коробе", "На полках (Физ, шт)", "Лимит FBS"]],
        column_config={"Фото": st.column_config.ImageColumn("Фото товара", width="small")},
        use_container_width=True, disabled=True, hide_index=True
    )
    
    st.write("---")
    st.subheader("🔄 Быстрая корректировка лимитов продаж FBS")
    col_l1, col_l2, col_l3 = st.columns(3)
    with col_l1:
        sku_manage = st.selectbox("Выберите SKU для изменения лимита:", list(sku_options.keys()), key="man_sku")
        m_key = sku_options[sku_manage]
    with col_l2:
        new_fbs_limit = st.number_input("Укажите новый лимит:", min_value=0, value=int(st.session_state.wms_inventory[m_key]['fbs_limit']))
    with col_l3:
        st.write("##")
        if st.button("🚀 Обновить лимиты по API", use_container_width=True):
            st.session_state.wms_inventory[m_key]['fbs_limit'] = new_fbs_limit
            st.success("Лимиты изменены успешно.")
            st.rerun()

# ВКЛАДКА 3: СЧЕТА И БИЛЛИНГ
with tab_billing:
    st.subheader("📅 Настройка произвольного периода и выгрузка отчетов")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        custom_range = st.date_input("Укажите диапазон дат отчета (с и по):", value=(st.session_state.start_period, st.session_state.end_period), max_value=today_date, key="calendar_billing")
        if isinstance(custom_range, tuple) and len(custom_range) == 2:
            st.session_state.start_period, st.session_state.end_period = custom_range
        days_in_period = (st.session_state.end_period - st.session_state.start_period).days + 1
        st.success(f"Выбрано дней: **{days_in_period}**")

    with col_b2:
        st.write("##")
        df_excel_ready = df_stocks_matrix[["Артикул продавца", "Название товара", "На полках (Физ, шт)", "Объем (м³)"]].copy()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_excel_ready.to_excel(writer, index=False, sheet_name='Отчет WMS Хранение')
        st.download_button(label=f"📥 Скачать отчет в Excel", data=buffer.getvalue(), file_name=f"wms_3pl_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    st.write("---")
    st.subheader("🧾 Детализированный финансовый счет за выбранный период")
    total_storage_cost_period = total_warehouse_m3 * st.session_state.m3_rate * days_in_period
    simulated_fbs_orders = 5
    total_processing_cost_period = simulated_fbs_orders * st.session_state.fbs_processing_rate
    grand_total_period = total_storage_cost_period + total_processing_cost_period

    billing_period_data = [
        {"Услуга фулфилмента": "Ответственное хранение объема груза на полках", "База расчета": f"{total_warehouse_m3:.4f} м³ × {days_in_period} дн.", "Тарифная ставка": f"{st.session_state.m3_rate:.2f} ₽ за 1 м³ / сутки", "Итого к списанию (₽)": f"{total_storage_cost_period:.2f} ₽"},
        {"Услуга фулфилмента": "Сборка, упаковка и маркировка заказов FBS", "База расчета": f"{simulated_fbs_orders} шт. обработано", "Тарифная ставка": f"{st.session_state.fbs_processing_rate:.2f} ₽ за 1 заказ", "Итого к списанию (₽)": f"{total_processing_cost_period:.2f} ₽"}
    ]
    st.table(pd.DataFrame(billing_period_data))
    st.success(f"💰 **СУММАРНЫЙ СЧЕТ К СПИСАНИЮ С БАЛАНСА СЕЛЛЕРА ЗА ПЕРИОД:** **{grand_total_period:.2f} ₽**")

# ВКЛАДКА 4: НАСТРОЙКИ API
with tab_api:
    st.subheader("🔑 Панель интеграции и управление ценообразованием 3PL")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("**Настройка базовых тарифов фулфилмента**")
        st.session_state.m3_rate = st.number_input("Стоимость хранения 1 м³ груза в сутки (₽):", min_value=0.0, value=float(st.session_state.m3_rate), step=1.0)
        st.session_state.fbs_processing_rate = st.number_input("Стоимость обработки одного заказа FBS (₽):", min_value=0.0, value=float(st.session_state.fbs_processing_rate), step=1.0)
    with col_t2:
        st.markdown("**Авторизация личных кабинетов маркетплейсов**")
        input_wb = st.text_input("Введите API Токен WB (тип 'Контент'):", type="password", value=wb_token)
        input_oz_id = st.text_input("Введите Ozon Client-ID:", value=ozon_client_id)
        input_oz_key = st.text_input("Введите Ozon API Key:", type="password", value=ozon_api_key)
        if st.button("💾 Сохранить и подключить ключи интеграции", use_container_width=True):
            st.session_state.wb_token_saved = input_wb
            st.session_state.ozon_id_saved = input_oz_id
            st.session_state.ozon_key_saved = input_oz_key
            st.success("Ключи сохранены! Перезапустите страницу.")
            st.rerun()
