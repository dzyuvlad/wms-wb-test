import streamlit as st
import pandas as pd
import datetime
import requests
import io

# Настройка страницы WMS
st.set_page_config(page_title="WMS Сквозной ОМС", layout="wide", page_icon="🌐")

st.title("🌐 Мультиканальная WMS: Справочник связок и мониторинг ручных остатков FBS")
st.write(f"Последняя синхронизация баз данных: `{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`")

# --- ИНИЦИАЛИЗАЦИЯ ДИНАМИЧЕСКИХ БАЗ ДАННЫХ (ФУНДАМЕНТ OMS) ---
# База 1: Справочник физических товаров на вашем складе (Внутренние артикулы ФФ)
if 'wms_ff_inventory' not in st.session_state:
    st.session_state.wms_ff_inventory = {
        'ФФ-СУШИЛКА-01': {
            'name': 'Сушилка для обуви электрическая XL',
            'length_cm': 25.0, 'width_cm': 15.0, 'height_cm': 10.0,
            'boxes': 5, 'pcs_in_box': 20, 'physical_stock': 100, 'fbo_allocated': 20
        }
    }

# База 2: Справочник связок (Маппинг) внешних кабинетов под ваш ФФ-код
if 'wms_mapping_rules' not in st.session_state:
    st.session_state.wms_mapping_rules = [
        {"Внутренний артикул ФФ": "ФФ-СУШИЛКА-01", "Магазин": "Wildberries (Кабинет 1)", "Артикул продавца": "001", "Баркод": "4607123456011"},
        {"Внутренний артикул ФФ": "ФФ-СУШИЛКА-01", "Магазин": "Ozon (Кабинет 1)", "Артикул продавца": "сушилка1", "Баркод": "4607123456022"},
    ]

# База 3: Внешние карточки с остатками, проставленными менеджером вручную на маркетплейсах
if 'api_pulled_cards' not in st.session_state:
    st.session_state.api_pulled_cards = [
        {"Магазин": "Wildberries (Кабинет 1)", "Артикул продавца": "001", "Название на витрине": "Сушилка обувная электрическая", "Баркод": "4607123456011", "Ручной остаток FBS на МП": 15},
        {"Магазин": "Wildberries (Кабинет 2)", "Артикул продавца": "WB-SU-DRY", "Название на витрине": "Сушилка для обуви бытовая", "Баркод": "4607123456033", "Ручной остаток FBS на МП": 0},
        {"Магазин": "Ozon (Кабинет 1)", "Артикул продавца": "сушилка1", "Название на витрине": "Электросушилка для сапог", "Баркод": "4607123456022", "Ручной остаток FBS на МП": 20},
        {"Магазин": "Ozon (Кабинет 2)", "Артикул продавца": "OZ-DRY-CLEAN", "Название на витрине": "Сушилка + дезинфектор", "Баркод": "4607123456044", "Ручной остаток FBS на МП": 5},
    ]

if 'wms_receipt_history' not in st.session_state: st.session_state.wms_receipt_history = []  
if 'm3_rate' not in st.session_state: st.session_state.m3_rate = 50.0
if 'fbs_processing_rate' not in st.session_state: st.session_state.fbs_processing_rate = 35.0
if 'piece_receive_rate' not in st.session_state: st.session_state.piece_receive_rate = 5.0     
if 'box_unload_rate' not in st.session_state: st.session_state.box_unload_rate = 20.0       

today_date = datetime.date.today()
if 'start_period' not in st.session_state: st.session_state.start_period = today_date - datetime.timedelta(days=6)
if 'end_period' not in st.session_state: st.session_state.end_period = today_date
# --- СОЗДАНИЕ СТРУКТУРЫ ВКЛАДОК ---
tab_receive, tab_mapping, tab_stocks, tab_billing, tab_api = st.tabs([
    "📥 Поартикульная Приемка", "🔗 Конструктор Связок (Маппинг)", "📊 Единый Сток (Матрица)", "📅 Счета и 3PL-Биллинг", "🔑 Настройки API и Тарифы"
])

# ВКЛАДКА 1: ПРИЕМКА ТОВАРА ПО ВНУТРЕННИМ КОДАМ ФУЛФИЛМЕНТА
with tab_receive:
    st.subheader("📥 Поартикульный приход груза под внутренние коды склада (ФФ)")
    existing_ff_skus = list(st.session_state.wms_ff_inventory.keys())
    col_r1, col_rec2 = st.columns(2)
    
    with col_r1:
        st.markdown("**1. Выберите или создайте внутренний ФФ-Артикул склада**")
        select_ff = st.selectbox("Внутренний код товара (ФФ):", existing_ff_skus + ["+ Создать новый ФФ-Артикул"])
        if select_ff == "+ Создать новый ФФ-Артикул":
            target_ff_sku = st.text_input("Задайте новый ФФ-код:", value="ФФ-ТОВАР-02")
            ff_name = st.text_input("Описание товара для склада:", value="Сушилка для обуви с УФ-лампой")
            c_l = st.number_input("Длина упаковки (см):", min_value=0.1, value=20.0)
            c_w = st.number_input("Ширина упаковки (см):", min_value=0.1, value=15.0)
            c_h = st.number_input("Высота упаковки (см):", min_value=0.1, value=10.0)
        else:
            target_ff_sku = select_ff
            ff_name = st.session_state.wms_ff_inventory[select_ff]['name']
            c_l = st.session_state.wms_ff_inventory[select_ff]['length_cm']
            c_w = st.session_state.wms_ff_inventory[select_ff]['width_cm']
            c_h = st.session_state.wms_ff_inventory[select_ff]['height_cm']
            st.info(f"📋 Выбран товар: **{ff_name}** | {c_l}x{c_w}x{c_h} см")

    with col_rec2:
        st.markdown("**2. Ввод количества новой партии (Короба × Вложение)**")
        input_boxes = st.number_input("Количество принятых коробов (шт):", min_value=0, value=0, step=1)
        input_pcs_in_box = st.number_input("Вложение (штук внутри одного короба):", min_value=1, value=20, step=1)
        calculated_total_pcs = input_boxes * input_pcs_in_box
        cost_unload = input_boxes * st.session_state.box_unload_rate
        cost_check = calculated_total_pcs * st.session_state.piece_receive_rate
        total_receipt_cost = cost_unload + cost_check
        
        st.markdown(f"### 📐 Итого к зачислению на склад: **{calculated_total_pcs} шт.**")
        st.warning(f"💰 Логистика прихода: Разгрузка {cost_unload:.2f} ₽ + Обработка {cost_check:.2f} ₽ = **{total_receipt_cost:.2f} ₽**")
        
        if st.button("📦 Утвердить накладную приемки по ФФ", use_container_width=True):
            if calculated_total_pcs > 0:
                if target_ff_sku not in st.session_state.wms_ff_inventory:
                    st.session_state.wms_ff_inventory[target_ff_sku] = {
                        'name': ff_name, 'length_cm': c_l, 'width_cm': c_w, 'height_cm': c_h,
                        'boxes': input_boxes, 'pcs_in_box': input_pcs_in_box, 'physical_stock': calculated_total_pcs, 'fbo_allocated': 0
                    }
                else:
                    st.session_state.wms_ff_inventory[target_ff_sku]['boxes'] += input_boxes
                    st.session_state.wms_ff_inventory[target_ff_sku]['physical_stock'] += calculated_total_pcs
                st.session_state.wms_receipt_history.append({
                    "Дата операции": today_date, "Артикул": target_ff_sku, "Разгружено коробов": input_boxes, "Принято штук": calculated_total_pcs,
                    "Сумма за разгрузку": cost_unload, "Сумма за обработку": cost_check, "Итого за накладную": total_receipt_cost
                })
                st.success(f"Товар успешно оприходован.")
                st.rerun()

# ВКЛАДКА 2: КОНСТРУКТОР СВЯЗОК (МАППИНГ)
with tab_mapping:
    st.subheader("🔗 Конструктор связок: Объединение внешних артикулов маркетплейсов под ваш ФФ-код")
    col_map1, col_map2 = st.columns(2)
    with col_map1:
        map_ff_sku = st.selectbox("Внутренний артикул фулфилмента (ФФ):", list(st.session_state.wms_ff_inventory.keys()), key="map_ff")
        st.write(f"Физический остаток на ваших полках: **{st.session_state.wms_ff_inventory[map_ff_sku]['physical_stock']} шт.**")
    with col_map2:
        api_options = {f"[{c['Магазин']}] SKU: {c['Артикул продавца']} | {c['Название на витрине']}": idx for idx, c in enumerate(st.session_state.api_pulled_cards)}
        selected_api_card_idx = st.selectbox("Внешняя карточка из API (WB / Ozon):", list(api_options.keys()))
        chosen_card = st.session_state.api_pulled_cards[api_options[selected_api_card_idx]]
        
    if st.button("🔗 Объединить в Единый Сток (Создать связку)", use_container_width=True):
        duplicate = any(r['Магазин'] == chosen_card['Магазин'] and r['Артикул продавца'] == chosen_card['Артикул продавца'] for r in st.session_state.wms_mapping_rules)
        if not duplicate:
            st.session_state.wms_mapping_rules.append({"Внутренний артикул ФФ": map_ff_sku, "Магазин": chosen_card['Магазин'], "Артикул продавца": chosen_card['Артикул продавца'], "Баркод": chosen_card['Баркод']})
            st.success(f"Успешно объединено!")
            st.rerun()
        else: st.error("Эта карточка уже привязана!")
    st.write("---")
    st.markdown("**📂 Действующие правила маппинга (Справочник связок)**")
    st.table(pd.DataFrame(st.session_state.wms_mapping_rules))
# ВКЛАДКА 3: МАТРИЦА ЕДИНОГО СТОКА OMS (ТОЛЬКО ОТОБРАЖЕНИЕ РУЧНЫХ FBS ИЗ API)
with tab_stocks:
    st.subheader("📊 Оперативная мультиканальная матрица Единого Стока")
    st.info("🔎 **Справочный мониторинг:** Остатки FBS проставляются менеджером вручную на самих маркетплейсах. WMS по API считывает эти цифры для визуализации и сквозного контроля остатков.")
    
    rows_unified = []
    total_warehouse_m3 = 0.0
    simulated_fbs_orders = 5  # Условные заказы покупателей по FBS
    
    for ff_sku, data in st.session_state.wms_ff_inventory.items():
        # Математика физического остатка на полках фулфилмента (Приняли - отгрузили FBO - отгрузили по FBS заказам)
        phys_stock_on_shelves = max(0, data['physical_stock'] - data['fbo_allocated'] - simulated_fbs_orders)
        
        # Считаем сумму ручных FBS остатков по всем привязанным кабинетам маркетплейсов для этого ФФ-товара
        total_live_fbs_on_marketplaces = 0
        connected_channels_list = []
        
        for rule in st.session_state.wms_mapping_rules:
            if rule['Внутренний артикул ФФ'] == ff_sku:
                # Ищем карточку в базе API и забираем ручной остаток, проставленный менеджером
                for card in st.session_state.api_pulled_cards:
                    if card['Магазин'] == rule['Магазин'] and card['Артикул продавца'] == rule['Артикул продавца']:
                        mp_stock = card.get('Ручной остаток FBS на МП', 0)
                        total_live_fbs_on_marketplaces += mp_stock
                        connected_channels_list.append(f"{rule['Магазин']} (SKU: {rule['Артикул продавца']} | В наличии на МП: {mp_stock} шт.)")
        
        channels_str = ", \n".join(connected_channels_list) if connected_channels_list else "⚠️ Нет привязанных витрин"
        
        unit_m3 = (data['length_cm'] * data['width_cm'] * data['height_cm']) / 1000000
        total_sku_m3 = unit_m3 * phys_stock_on_shelves
        total_warehouse_m3 += total_sku_m3
        
        rows_unified.append({
            "Внутренний Код ФФ": ff_sku, "Описание товара": data['name'], "Габариты упаковки": f"{data['length_cm']}x{data['width_cm']}x{data['height_cm']} см",
            "📦 НА ВАШИХ ПОЛКАХ (ФИЗ, шт)": phys_stock_on_shelves, "Сумма остатков FBS на всех МП": total_live_fbs_on_marketplaces, "Остаток на FBO маркетплейсов": data['fbo_allocated'], "Детализация витрин (Ручной ввод менеджера)": channels_str
        })
        
    df_unified_matrix = pd.DataFrame(rows_unified)
    k1, k2, k3 = st.columns(3)
    with k1: st.metric("Всего физических позиций ФФ", len(df_unified_matrix))
    with k2: st.metric("Всего штук на полках склада", int(df_unified_matrix["📦 НА ВАШИХ ПОЛКАХ (ФИЗ, шт)"].sum()))
    with k3: st.metric("Активный платный объем (м³)", f"{total_warehouse_m3:.4f} м³")
    st.write("---")
    st.dataframe(df_unified_matrix, use_container_width=True, hide_index=True)

# ВКЛАДКА 4: СЧЕТА И ПООПЕРАЦИОННЫЙ БИЛЛИНГ
with tab_billing:
    st.subheader("📅 Финансовая отчетность по периодам (Календарь)")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        custom_range = st.date_input("Выберите интересующий диапазон дат:", value=(st.session_state.start_period, st.session_state.end_period), max_value=today_date, key="calendar_billing")
        if isinstance(custom_range, tuple) and len(custom_range) == 2: st.session_state.start_period, st.session_state.end_period = custom_range
        days_in_period = (st.session_state.end_period - st.session_state.start_period).days + 1
        st.success(f"Период расчета: **{days_in_period} дн.**")
    with col_b2:
        st.write("##")
        df_excel_ready = df_unified_matrix[["Внутренний Код ФФ", "Описание товара", "📦 НА ВАШИХ ПОЛКАХ (ФИЗ, шт)"]].copy()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_excel_ready.to_excel(writer, index=False)
        st.download_button(label="📥 Скачать сводный отчет в Excel", data=buffer.getvalue(), file_name="wms_3pl_billing.xlsx", use_container_width=True)

    df_receipt_history = pd.DataFrame(st.session_state.wms_receipt_history) if st.session_state.wms_receipt_history else pd.DataFrame(columns=["Дата операции", "Разгружено коробов", "Принято штук", "Сумма за разгрузку", "Сумма за обработку", "Итого за накладную"])
    total_boxes_unloaded_period = 0
    total_pcs_received_period = 0
    total_receipt_billing_period = 0.0
    
    if not df_receipt_history.empty:
        df_receipt_filtered = df_receipt_history[(df_receipt_history['Дата операции'] >= st.session_state.start_period) & (df_receipt_history['Дата операции'] <= st.session_state.end_period)]
        total_boxes_unloaded_period = df_receipt_filtered['Разгружено коробов'].sum()
        total_pcs_received_period = df_receipt_filtered['Принято штук'].sum()
        total_receipt_billing_period = df_receipt_filtered['Итого за накладную'].sum()
        st.write("---")
        st.subheader("📋 Operational journal")
        df_receipt_disp = df_receipt_filtered.copy()
        df_receipt_disp['Дата операции'] = df_receipt_disp['Дата операции'].apply(lambda x: x.strftime('%Y-%m-%d'))
        st.dataframe(df_receipt_disp, use_container_width=True, hide_index=True)

    st.write("---")
    st.subheader("🧾 Итоговый детализированный 3PL-счет за выбранный срок")
    total_storage_cost_period = total_warehouse_m3 * st.session_state.m3_rate * days_in_period
    total_processing_cost_period = simulated_fbs_orders * st.session_state.fbs_processing_rate
    grand_total_period = total_storage_cost_period + total_processing_cost_period + total_receipt_billing_period

    billing_period_data = [
        {"Услуга фулфилмента": "Ответственное хранение объема груза на полках", "База расчета": f"{total_warehouse_m3:.4f} м³ × {days_in_period} дн.", "Тарифная ставка": f"{st.session_state.m3_rate:.2f} ₽ за 1 м³ / сутки", "Итого к списанию (₽)": f"{total_storage_cost_period:.2f} ₽"},
        {"Услуга фулфилмента": "Сборка, упаковка и маркировка заказов по FBS", "База расчета": f"{simulated_fbs_orders} шт. обработано", "Тарифная ставка": f"{st.session_state.fbs_processing_rate:.2f} ₽ за 1 заказ", "Итого к списанию (₽)": f"{total_processing_cost_period:.2f} ₽"},
        {"Услуга фулфилмента": "Разгрузка прибывших коробов с машиной", "База расчета": f"{total_boxes_unloaded_period} кор. разгружено", "Тарифная ставка": f"{st.session_state.box_unload_rate:.2f} ₽ за 1 короб", "Итого к списанию (₽)": f"{df_receipt_history[(df_receipt_history['Дата операции'] >= st.session_state.start_period) & (df_receipt_history['Дата операции'] <= st.session_state.end_period)]['Сумма за разгрузку'].sum() if not df_receipt_history.empty else 0:.2f} ₽"},
        {"Услуга фулфилмента": "Поштучная обработка, пересчет и стикерование товара", "База расчета": f"{total_pcs_received_period} шт. оприходовано", "Тарифная ставка": f"{st.session_state.piece_receive_rate:.2f} ₽ за 1 штуку", "Итого к списанию (₽)": f"{df_receipt_history[(df_receipt_history['Дата операции'] >= st.session_state.start_period) & (df_receipt_history['Дата операции'] <= st.session_state.end_period)]['Сумма за обработку'].sum() if not df_receipt_history.empty else 0:.2f} ₽"}
    ]
    st.table(pd.DataFrame(billing_period_data))
    st.success(f"💰 **ОБЩИЙ СЧЕТ К СУММАРНОМУ СПИСАНИЮ С БАЛАНСА СЕЛЛЕРА ЗА ПЕРИОД:** **{grand_total_period:.2f} ₽**")

# ВКЛАДКА 5: НАСТРОЙКИ
with tab_api:
    st.subheader("🔑 Панель интеграции и тарифов 3PL")
    st.session_state.m3_rate = st.number_input("Стоимость хранения 1 м³ груза в сутки (₽):", min_value=0.0, value=float(st.session_state.m3_rate), step=1.0)
    st.session_state.fbs_processing_rate = st.number_input("Стоимость сборки одного заказа FBS (₽):", min_value=0.0, value=float(st.session_state.fbs_processing_rate), step=1.0)
    st.session_state.piece_receive_rate = st.number_input("Тариф за поштучную обработку 1 единицы товара (₽):", min_value=0.0, value=float(st.session_state.piece_receive_rate), step=0.5)
    st.session_state.box_unload_rate = st.number_input("Тариф за физическую разгрузку 1 короба с машины (₽):", min_value=0.0, value=float(st.session_state.box_unload_rate), step=1.0)
