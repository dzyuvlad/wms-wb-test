import streamlit as st
import pandas as pd
import datetime
import requests
import io

# Настройка страницы WMS
st.set_page_config(page_title="WMS Фикс Биллинга и Хронологии", layout="wide", page_icon="📦")

st.title("WMS")
st.write(f"Последняя синхронизация баз данных: `{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`")

# --- ИНИЦИАЛИЗАЦИЯ ДИНАМИЧЕСКИХ БАЗ ДАННЫХ (ФУНДАМЕНТ OMS) ---
if 'wms_ff_inventory' not in st.session_state:
    st.session_state.wms_ff_inventory = {
        'ФФ-СУШИЛКА-01': {
            'name': 'Сушилка для обуви электрическая XL',
            'length_cm': 25.0, 'width_cm': 15.0, 'height_cm': 10.0,
            'boxes': 5, 'pcs_in_box': 20, 'physical_stock': 100, 'fbo_allocated': 20
        }
    }

if 'wms_mapping_rules' not in st.session_state:
    st.session_state.wms_mapping_rules = [
        {"Внутренний артикул ФФ": "ФФ-СУШИЛКА-01", "Магазин": "Wildberries (Кабинет 1)", "Артикул продавца": "001", "Баркод": "4607123456011"},
        {"Внутренний артикул ФФ": "ФФ-СУШИЛКА-01", "Магазин": "Ozon (Кабинет 1)", "Артикул продавца": "сушилка1", "Баркод": "4607123456022"},
    ]

if 'api_pulled_cards' not in st.session_state:
    st.session_state.api_pulled_cards = [
        {"Магазин": "Wildberries (Кабинет 1)", "Артикул продавца": "001", "Название на витрине": "Сушилка обувная электрическая", "Баркод": "4607123456011", "Ручной остаток FBS на МП": 15},
        {"Магазин": "Wildberries (Кабинет 2)", "Артикул продавца": "WB-SU-DRY", "Название на витрине": "Сушилка для обуви бытовая", "Баркод": "4607123456033", "Ручной остаток FBS на МП": 0},
        {"Магазин": "Ozon (Кабинет 1)", "Артикул продавца": "сушилка1", "Название на витрине": "Электросушилка для сапог", "Баркод": "4607123456022", "Ручной остаток FBS на МП": 20},
        {"Магазин": "Ozon (Кабинет 2)", "Артикул продавца": "OZ-DRY-CLEAN", "Название на витрине": "Сушилка + дезинфектор", "Баркод": "4607123456044", "Ручной остаток FBS на МП": 5},
    ]

today_date = datetime.date.today()
now_time = datetime.datetime.now()

if 'wms_receipt_history' not in st.session_state:
    st.session_state.wms_receipt_history = [
        {
            "Дата операции": today_date, "Время приемки": "22:45:10",
            "Внутренний Артикул ФФ": "ФФ-СУШИЛКА-01", "Разгружено коробов (шт)": 3, "Принято товара (шт)": 60,
            "Сумма за разгрузку": 60.0, "Сумма за обработку": 300.0, "Итого за накладную": 360.0
        },
        {
            "Дата операции": today_date - datetime.timedelta(days=1), "Время приемки": "11:15:30",
            "Внутренний Артикул ФФ": "ФФ-СУШИЛКА-01", "Разгружено коробов (шт)": 2, "Принято товара (шт)": 40,
            "Сумма за разгрузку": 40.0, "Сумма за обработку": 200.0, "Итого за накладную": 240.0
        }
    ]

if 'm3_rate' not in st.session_state: st.session_state.m3_rate = 50.0
if 'fbs_processing_rate' not in st.session_state: st.session_state.fbs_processing_rate = 35.0
if 'piece_receive_rate' not in st.session_state: st.session_state.piece_receive_rate = 5.0     
if 'box_unload_rate' not in st.session_state: st.session_state.box_unload_rate = 20.0       

if 'wb_token_saved' not in st.session_state: st.session_state.wb_token_saved = ''
if 'ozon_id_saved' not in st.session_state: st.session_state.ozon_id_saved = ''
if 'ozon_key_saved' not in st.session_state: st.session_state.ozon_key_saved = ''

if 'start_period' not in st.session_state: st.session_state.start_period = today_date - datetime.timedelta(days=6)
if 'end_period' not in st.session_state: st.session_state.end_period = today_date
# --- СОЗДАНИЕ СТРУКТУРЫ ВКЛАДОК ---
tab_receive, tab_stocks, tab_billing, tab_api = st.tabs([
    "📥 Приемка и Привязка по API", "📊 Текущие Остатки (Матрица)", "📅 Счета и 3PL-Биллинг", "🔑 Настройки API и Тарифы"
])

# ОБЪЕДИНЕННАЯ ВКЛАДКА: ПОАРТИКУЛЬНЫЙ ПРИХОД + СВЯЗЫВАНИЕ КАРТОЧЕК
with tab_receive:
    st.subheader("📥 Шаг 1: Выберите товар склада (или зарегистрируйте новый)")
    existing_ff_skus = list(st.session_state.wms_ff_inventory.keys())
    
    col_step1, col_step2 = st.columns(2)
    with col_step1:
        select_ff = st.selectbox("Выберите внутренний артикул ФФ:", existing_ff_skus + ["+ Создать новый ФФ-Артикул"])
        if select_ff == "+ Создать новый ФФ-Артикул":
            target_ff_sku = st.text_input("Присвойте новый код ФФ:", value="ФФ-ТОВАР-02")
            ff_name = st.text_input("Введите название товара для склада:", value="Сушилка для обуви с УФ-лампой")
            c_l = st.number_input("Длина упаковки (см):", min_value=0.1, value=20.0)
            c_w = st.number_input("Ширина упаковки (см):", min_value=0.1, value=15.0)
            c_h = st.number_input("Высота упаковки (см):", min_value=0.1, value=10.0)
        else:
            target_ff_sku = select_ff
            ff_name = st.session_state.wms_ff_inventory[select_ff]['name']
            c_l = st.number_input("Длина упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['length_cm']))
            c_w = st.number_input("Ширина упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['width_cm']))
            c_h = st.number_input("Высота упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['height_cm']))

    with col_step2:
        st.markdown("**🔗 Шаг 2: Привязка карточек маркетплейсов к этому товару**")
        search_query = st.text_input("🔍 Умный поиск по артикулу продавца:", value="", help="Вбейте артикул с накладной для быстрой фильтрации")
        
        api_options = {f"[{c['Магазин']}] SKU: {c['Артикул продавца']} | {c['Название на витрине']}": idx for idx, c in enumerate(st.session_state.api_pulled_cards)}
        
        if search_query:
            filtered_api_options = {lbl: idx for lbl, idx in api_options.items() if search_query.strip().lower() in st.session_state.api_pulled_cards[idx]['Артикул продавца'].lower()}
        else:
            filtered_api_options = api_options

        pre_selected = []
        for rule in st.session_state.wms_mapping_rules:
            if rule['Внутренний артикул ФФ'] == target_ff_sku:
                for label, idx in api_options.items():
                    card = st.session_state.api_pulled_cards[idx]
                    if card['Магазин'] == rule['Магазин'] and card['Артикул продавца'] == rule['Артикул продавца']:
                        pre_selected.append(label)
        
        selected_labels = st.multiselect("Выберите карточки маркетплейсов:", list(filtered_api_options.keys()), default=[p for p in pre_selected if p in filtered_api_options])
        
        if st.button("🔗 Утвердить общую группу связок Единого Стока", use_container_width=True):
            st.session_state.wms_mapping_rules = [r for r in st.session_state.wms_mapping_rules if r['Внутренний артикул ФФ'] != target_ff_sku]
            for label in selected_labels:
                card_idx = api_options[label]
                chosen_card = st.session_state.api_pulled_cards[card_idx]
                st.session_state.wms_mapping_rules.append({"Внутренний артикул ФФ": target_ff_sku, "Магазин": chosen_card['Магазин'], "Артикул продавца": chosen_card['Артикул продавца'], "Баркод": chosen_card['Баркод']})
            st.success(f"Группа связок Единого Стока для '{target_ff_sku}' успешно обновлена!")
            st.rerun()

    st.write("---")
    st.subheader("📦 Шаг 3: Ввод принятой партии и Контроль кубатуры")
    st.info("📏 **Контроль кубатуры**")
    
    col_qty1, col_qty2 = st.columns(2)
    with col_qty1:
        input_boxes = st.number_input("Сколько коробов сняли с машины (шт):", min_value=0, value=0, step=1)
        input_pcs_in_box = st.number_input("Сколько штук лежит внутри ОДНОГО короба (вложение):", min_value=1, value=20, step=1)
    
    with col_qty2:
        calculated_total_pcs = input_boxes * input_pcs_in_box
        cost_unload = input_boxes * st.session_state.box_unload_rate
        cost_check = calculated_total_pcs * st.session_state.piece_receive_rate
        total_receipt_cost = cost_unload + cost_check
        unit_m3_calc = (c_l * c_w * c_h) / 1000000
        total_m3_calc = unit_m3_calc * calculated_total_pcs
        
        st.markdown(f"📈 Будет добавлено на баланс: **{calculated_total_pcs} шт.** ({total_m3_calc:.4f} м³)")
        st.write(f"💰 **Логистический счет за накладную:** разгрузка {cost_unload:.2f} ₽ + обработка {cost_check:.2f} ₽ = **{total_receipt_cost:.2f} ₽**")
        
        if st.button("📦 УТВЕРДИТЬ АКТ ПРИЕМКИ И ВЫСТАВИТЬ СЧЕТ", use_container_width=True, type="primary"):
            if calculated_total_pcs > 0:
                current_time_stamp = datetime.datetime.now()
                st.session_state.wms_ff_inventory[target_ff_sku] = {
                    'name': ff_name, 'length_cm': c_l, 'width_cm': c_w, 'height_cm': c_h,
                    'boxes': st.session_state.wms_ff_inventory.get(target_ff_sku, {}).get('boxes', 0) + input_boxes,
                    'pcs_in_box': input_pcs_in_box,
                    'physical_stock': st.session_state.wms_ff_inventory.get(target_ff_sku, {}).get('physical_stock', 0) + calculated_total_pcs,
                    'fbo_allocated': st.session_state.wms_ff_inventory.get(target_ff_sku, {}).get('fbo_allocated', 0)
                }
                st.session_state.wms_receipt_history.append({
                    "Дата операции": current_time_stamp.date(), "Время приемки": current_time_stamp.strftime('%H:%M:%S'), "Внутренний Артикул ФФ": target_ff_sku,
                    "Разгружено коробов (шт)": input_boxes, "Принято товара (шт)": calculated_total_pcs, "Сумма за разгрузку": cost_unload, "Сумма за обработку": cost_check, "Итого за накладную": total_receipt_cost
                })
                st.success("Акт успешно записан!")
                st.rerun()
# ВКЛАДКА 2: МАТРИЦА ЕДИНОГО СТОКА (ИСПРАВЛЕНО НАЗВАНИЕ КОЛОНКИ ДЛЯ ИСКЛЮЧЕНИЯ KEYERROR)
with tab_stocks:
    st.subheader("📊 Оперативная мультиканальная матрица Единого Стока")
    
    rows_unified = []
    total_warehouse_m3 = 0.0
    simulated_fbs_orders = 5  
    
    for ff_sku, data in st.session_state.wms_ff_inventory.items():
        total_live_fbs_on_marketplaces = 0
        connected_channels_list = []
        
        for rule in st.session_state.wms_mapping_rules:
            if rule['Внутренний артикул ФФ'] == ff_sku:
                for card in st.session_state.api_pulled_cards:
                    if card['Магазин'] == rule['Магазин'] and card['Артикул продавца'] == rule['Артикул продавца']:
                        mp_stock = int(card.get('Ручной остаток FBS на МП', 0)) 
                        total_live_fbs_on_marketplaces += mp_stock
                        connected_channels_list.append(f"{rule['Магазин']} (SKU: {rule['Артикул продавца']} | Сток: {mp_stock} шт.)")
        
        # Чистый физический остаток на полках склада
        phys_stock_on_shelves = max(0, data['physical_stock'] - data['fbo_allocated'] - simulated_fbs_orders)
        
        # Полная сумма штук, занимающих место на ваших полках (включая FBS лимиты)
        total_billable_pcs_including_fbs = phys_stock_on_shelves + total_live_fbs_on_marketplaces
        
        unit_m3 = (data['length_cm'] * data['width_cm'] * data['height_cm']) / 1000000
        total_sku_m3 = unit_m3 * total_billable_pcs_including_fbs
        total_warehouse_m3 += total_sku_m3
        
        channels_str = ", \n".join(connected_channels_list) if connected_channels_list else "⚠️ Нет привязанных витрин"
        
        # НАЗВАНИЕ КОЛОНКИ ИДЕАЛЬНО ВЫРАВНЕНО С ВЫВОДОМ НА ЭКРАН (УСТРАНЕНИЕ СБОЯ СТРОКИ 203)
        rows_unified.append({
            "Внутренний Код ФФ": ff_sku, 
            "Описание товара": data['name'], 
            "Габариты упаковки (ЗАМЕР СКЛАДА)": f"{data['length_cm']}x{data['width_cm']}x{data['height_cm']} см",
            "📦 НА ПОЛКАХ (Платное хранение, шт)": total_billable_pcs_including_fbs, 
            "Из них выставлено под FBS менеджером (шт)": total_live_fbs_on_marketplaces, 
            "Уехало на FBO маркетплейсов": data['fbo_allocated'], 
            "Детализация связанных витрин селлера": channels_str
        })
        
    if rows_unified:
        df_unified_matrix = pd.DataFrame(rows_unified)
        k1, k2, k3 = st.columns(3)
        with k1: st.metric("Всего позиций ФФ", len(df_unified_matrix))
        with k2: st.metric("Всего штук на платном хранении фулфилмента (Физ + FBS)", int(df_unified_matrix["📦 НА ПОЛКАХ (Платное хранение, шт)"].sum()))
        with k3: st.metric("Активный тарифицируемый объем (м³)", f"{total_warehouse_m3:.4f} м³")
        st.write("---")
        
        # ИСПРАВЛЕНО: Теперь названия колонок внутри квадратных скобок на 100% совпадают с rows_unified
        st.dataframe(
            df_unified_matrix[["Внутренний Код ФФ", "Описание товара", "Габариты упаковки (ЗАМЕР СКЛАДА)", "📦 НА ПОЛКАХ (Платное хранение, шт)", "Из них выставлено под FBS менеджером (шт)", "Уехало на FBO маркетплейсов", "Детализация связанных витрин селлера"]], 
            use_container_width=True, 
            hide_index=True
        )
    else: 
        st.info("Склад пуст. Проведите приемку в первой вкладке.")

# ВКЛАДКА 3: СЧЕТА И СКВОЗНОЙ ПООПЕРАЦИОННЫЙ БИЛЛИНГ С УЧЕТОМ ЖУРНАЛА ПРИХОДОВ ЗА ПЕРИОД
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
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer: pd.DataFrame(rows_unified).to_excel(writer, index=False)
        st.download_button(label="📥 Скачать сводный отчет в Excel", data=buffer.getvalue(), file_name="wms_3pl_billing.xlsx", use_container_width=True)

    df_receipt_history = pd.DataFrame(st.session_state.wms_receipt_history) if st.session_state.wms_receipt_history else pd.DataFrame(columns=["Дата операции", "Время приемки", "Внутренний Артикул ФФ", "Разгружено коробов (шт)", "Принято товара (шт)", "Сумма за разгрузку", "Сумма за обработку", "Итого за накладную"])
    
    total_boxes_unloaded_period = 0
    total_pcs_received_period = 0
    total_receipt_billing_period = 0.0
    
    if not df_receipt_history.empty:
        df_receipt_filtered = df_receipt_history[(df_receipt_history['Дата операции'] >= st.session_state.start_period) & (df_receipt_history['Дата операции'] <= st.session_state.end_period)]
        if not df_receipt_filtered.empty:
            total_boxes_unloaded_period = df_receipt_filtered['Разгружено коробов (шт)'].sum()
            total_pcs_received_period = df_receipt_filtered['Принято товара (шт)'].sum()
            total_receipt_billing_period = df_receipt_filtered['Итого за накладную'].sum()
            
            st.write("---")
            st.subheader("📋 Операционный журнал приходов (Поминутная хронология за выбранный период)")
            df_receipt_disp = df_receipt_filtered.copy()
            df_receipt_disp['Дата операции'] = df_receipt_disp['Дата операции'].apply(lambda x: x.strftime('%Y-%m-%d'))
            st.dataframe(df_receipt_disp, use_container_width=True, hide_index=True)

    st.write("---")
    st.subheader("🧾 Итоговый детализированный 3PL-счет за выбранный срок (Все операции + Хранение)")
    
    total_storage_cost_period = total_warehouse_m3 * st.session_state.m3_rate * days_in_period
    total_processing_cost_period = 5 * st.session_state.fbs_processing_rate
    grand_total_period = total_storage_cost_period + total_processing_cost_period + total_receipt_billing_period

    billing_period_data = [
        {"Услуга фулфилмента": "Ответственное хранение объема груза на полках (Включая остатки FBS)", "База расчета": f"{total_warehouse_m3:.4f} м³ × {days_in_period} дн.", "Тарифная ставка": f"{st.session_state.m3_rate:.2f} ₽ за 1 м³ / сутки", "Итого к списанию (₽)": f"{total_storage_cost_period:.2f} ₽"},
        {"Услуга фулфилмента": "Сборка, упаковка и маркировка заказов по FBS", "База расчета": "5 шт. обработано", "Тарифная ставка": f"{st.session_state.fbs_processing_rate:.2f} ₽ за 1 заказ", "Итого к списанию (₽)": f"{5 * st.session_state.fbs_processing_rate:.2f} ₽"},
        {"Услуга фулфилмента": "Разгрузка прибывших коробов с машиной (Акты из журнала приходов)", "База расчета": f"{total_boxes_unloaded_period} кор. зафиксировано", "Тарифная ставка": f"{st.session_state.box_unload_rate:.2f} ₽ за 1 короб", "Итого к списанию (₽)": f"{total_boxes_unloaded_period * st.session_state.box_unload_rate:.2f} ₽"},
        {"Услуга фулфилмента": "Поштучная обработка, пересчет и стикерование товара (Акты из журнала приходов)", "База расчета": f"{total_pcs_received_period} шт. зафиксировано", "Тарифная ставка": f"{st.session_state.piece_receive_rate:.2f} ₽ за 1 штуку", "Итого к списанию (₽)": f"{total_pcs_received_period * st.session_state.piece_receive_rate:.2f} ₽"}
    ]
    st.table(pd.DataFrame(billing_period_data))
    st.success(f"💰 **ОБЩИЙ СКВОЗНОЙ СЧЕТ К СУММАРНОМУ СПИСАНИЮ С БАЛАНСА СЕЛЛЕРА ЗА ПЕРИОД:** **{grand_total_period:.2f} ₽** (Все услуги прихода и FBS хранения учтены полностью)")

# ВКЛАДКА 4: НАСТРОЙКИ
with tab_api:
    st.subheader("🔑 Панель интеграции и тарифов 3PL")
    st.session_state.m3_rate = st.number_input("Стоимость хранения 1 м³ груза в сутки (₽):", min_value=0.0, value=float(st.session_state.m3_rate), step=1.0)
    st.session_state.fbs_processing_rate = st.number_input("Стоимость сборки одного заказа FBS (₽):", min_value=0.0, value=float(st.session_state.fbs_processing_rate), step=1.0)
    st.session_state.piece_receive_rate = st.number_input("Тариф за поштучную обработку 1 единицы товара (₽):", min_value=0.0, value=float(st.session_state.piece_receive_rate), step=0.5)
    st.session_state.box_unload_rate = st.number_input("Тариф за физическую разгрузку 1 короба с машины (₽):", min_value=0.0, value=float(st.session_state.box_unload_rate), step=1.0)
