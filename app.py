import streamlit as st
import pandas as pd
import datetime
import io

# Настройка страницы WMS
st.set_page_config(page_title="WMS Гибкие Тарифы OMS", layout="wide", page_icon="📦")

st.title("WMS")
st.write(f"Последняя синхронизация баз данных: `{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`")

# --- ПОЛНОЕ ОБНУЛЕНИЕ ВСЕХ БАЗ ДАННЫХ ДЛЯ ЧИСТОГО ТЕСТА С НУЛЯ ---
if 'wms_ff_inventory' not in st.session_state:
    st.session_state.wms_ff_inventory = {}

if 'wms_mapping_rules' not in st.session_state:
    st.session_state.wms_mapping_rules = []

if 'api_pulled_cards' not in st.session_state:
    st.session_state.api_pulled_cards = [
        {"Магазин": "Wildberries (Кабинет 1)", "Артикул продавца": "001", "Название на витрине": "Сушилка обувная электрическая", "Баркод": "4607123456011", "Ручной остаток FBS на МП": 15},
        {"Магазин": "Wildberries (Кабинет 2)", "Артикул продавца": "WB-SU-DRY", "Название на витрине": "Сушилка для обуви бытовая", "Баркод": "4607123456033", "Ручной остаток FBS на МП": 0},
        {"Магазин": "Ozon (Кабинет 1)", "Артикул продавца": "сушилка1", "Название на витрине": "Электросушилка для сапог", "Баркод": "4607123456022", "Ручной остаток FBS на МП": 20},
        {"Магазин": "Ozon (Кабинет 2)", "Артикул продавца": "OZ-DRY-CLEAN", "Название на витрине": "Сушилка + дезинфектор", "Баркод": "4607123456044", "Ручной остаток FBS на МП": 5},
    ]

if 'wms_fbs_custom_rates' not in st.session_state:
    st.session_state.wms_fbs_custom_rates = {}

today_date = datetime.date.today()

if 'wms_receipt_history' not in st.session_state:
    st.session_state.wms_receipt_history = []

# --- НОВАЯ БАЗА ДАННЫХ: ЖУРНАЛ ЗАФИКСИРОВАННЫХ ОПЛАТ (Клиент/Период) ---
if 'wms_payment_ledger' not in st.session_state:
    st.session_state.wms_payment_ledger = [] # Список словарей с оплаченными интервалами

if 'm3_rate' not in st.session_state: st.session_state.m3_rate = 50.0
if 'default_fbs_rate' not in st.session_state: st.session_state.default_fbs_rate = 35.0  
if 'default_piece_rate' not in st.session_state: st.session_state.default_piece_rate = 5.0

if 'wb_token_saved' not in st.session_state: st.session_state.wb_token_saved = ''
if 'ozon_id_saved' not in st.session_state: st.session_state.ozon_id_saved = ''
if 'ozon_key_saved' not in st.session_state: st.session_state.ozon_key_saved = ''

if 'start_period' not in st.session_state: st.session_state.start_period = today_date - datetime.timedelta(days=6)
if 'end_period' not in st.session_state: st.session_state.end_period = today_date

# --- СТРУКТУРА ИЗ 5 ИЗОЛИРОВАННЫХ ВКЛАДОК ---
tab_receive, tab_stocks, tab_billing, tab_rates, tab_api = st.tabs([
    "📥 Приемка и Привязка по API", 
    "📊 Текущие Остатки (Матрица)", 
    "📅 Счета и 3PL-Биллинг", 
    "💰 Управление Тарифами Склада",
    "🔑 Подключение Ключей API"
])
with tab_receive:
    st.subheader("📥 Шаг 1: Выберите товар склада (или зарегистрируйте новый)")
    existing_ff_skus = list(st.session_state.wms_ff_inventory.keys())
    
    col_step1, col_step2 = st.columns(2)
    with col_step1:
        select_ff = st.selectbox("Выберите внутренний артикул ФФ:", existing_ff_skus + ["+ Создать новый ФФ-Артикул"])
        if select_ff == "+ Создать новый ФФ-Артикул":
            target_ff_sku = st.text_input("Присвойте новый код ФФ:", value="ФФ-ТОВАР-01")
            ff_name = st.text_input("Введите название товара для склада:", value="Тестовый товар")
            c_l = st.number_input("Длина упаковки (см):", min_value=0.1, value=20.0)
            c_w = st.number_input("Ширина упаковки (см):", min_value=0.1, value=15.0)
            c_h = st.number_input("Высота упаковки (см):", min_value=0.1, value=10.0)
            sku_piece_rate = st.number_input("Фиксированный тариф за обработку 1 шт данного артикула (₽):", min_value=0.0, value=float(st.session_state.default_piece_rate), step=0.5, key="rate_new")
        else:
            target_ff_sku = select_ff
            ff_name = st.session_state.wms_ff_inventory[select_ff]['name']
            c_l = st.number_input("Длина упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['length_cm']))
            c_w = st.number_input("Ширина упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['width_cm']))
            c_h = st.number_input("Высота упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['height_cm']))
            saved_rate = st.session_state.wms_ff_inventory[select_ff].get('piece_rate', st.session_state.default_piece_rate)
            sku_piece_rate = st.number_input("Фиксированный тариф за обработку 1 шт данного артикула (₽):", min_value=0.0, value=float(saved_rate), step=0.5, key="rate_old")

    with col_step2:
        st.markdown("**🔗 Шаг 2: Привязка карточек маркетплейсов к этому товару**")
        search_query = st.text_input("🔍 Быстрый поиск по артикулу продавца:", value="", placeholder="Например: 001 или сушилка").strip().lower()
        
        api_options = {f"{c['Артикул продавца']} | {c['Название на витрине']} | [{c['Магазин']}]": idx for idx, c in enumerate(st.session_state.api_pulled_cards)}
        
        if search_query:
            filtered_api_options = {lbl: idx for lbl, idx in api_options.items() if search_query in st.session_state.api_pulled_cards[idx]['Артикул продавца'].lower()}
        else:
            filtered_api_options = api_options

        pre_selected = []
        for rule in st.session_state.wms_mapping_rules:
            if rule['Внутренний артикул ФФ'] == target_ff_sku:
                for label, idx in api_options.items():
                    card = st.session_state.api_pulled_cards[idx]
                    if card['Магазин'] == rule['Магазин'] and card['Артикул продавца'] == rule['Артикул продавца']:
                        pre_selected.append(label)
        
        selected_labels = st.multiselect("Выберите карточки маркетплейсов для объединения стока:", list(filtered_api_options.keys()), default=[p for p in pre_selected if p in filtered_api_options])

    st.write("---")
    st.subheader("📦 Шаг 3: Ввод принятой партии и Контроль кубатуры")
    
    col_qty1, col_qty2 = st.columns(2)
    with col_qty1:
        input_boxes = st.number_input("Сколько коробов сняли с машины (шт):", min_value=0, value=0, step=1)
        input_pcs_in_box = st.number_input("Сколько штук лежит внутри ОДНОГО короба (вложение):", min_value=1, value=20, step=1)
        box_unload_rate_input = st.number_input("Тариф за физическую разгрузку 1 короба с машины (₽):", min_value=0.0, value=60.0, step=5.0)
    
    with col_qty2:
        calculated_total_pcs = input_boxes * input_pcs_in_box
        cost_unload = input_boxes * box_unload_rate_input
        cost_check = calculated_total_pcs * sku_piece_rate
        total_receipt_cost = cost_unload + cost_check
        unit_m3_calc = (c_l * c_w * c_h) / 1000000
        total_m3_calc = unit_m3_calc * calculated_total_pcs
        
        st.markdown(f"📈 К зачислению на баланс: **{calculated_total_pcs} шт.** ({total_m3_calc:.4f} м³)")
        st.write(f"💰 Логистический счет: разгрузка {cost_unload:.2f} ₽ + обработка {cost_check:.2f} ₽ = **{total_receipt_cost:.2f} ₽**")
        
        if st.button("📦 СФОРМИРОВАТЬ АКТ ПРИЕМКИ ДЛЯ ПРОВЕРКИ", use_container_width=True, type="primary"):
            if calculated_total_pcs <= 0:
                st.error("❌ Ошибка: Невозможно сформировать акт с нулевым количеством товара!")
            else:
                st.session_state.show_confirmation_modal = True

    if st.session_state.get('show_confirmation_modal', False):
        st.markdown("---")
        st.markdown("### ⚠️ ПОДТВЕРЖДЕНИЕ ПРИЕМКИ: Проверьте данные перед записью!")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown(f"📂 **Физические параметры партии:**")
            st.markdown(f"* Внутренний код артикула: `{target_ff_sku}`")
            st.markdown(f"* Описание товара: **{ff_name}**")
            st.markdown(f"* Количество коробов: ` {input_boxes} шт. ` (разгрузка по {box_unload_rate_input:.2f} ₽/кор)")
            st.markdown(f"* Вложение внутри одного короба: ` {input_pcs_in_box} шт. `")
            st.markdown(f"## 📐 ИТОГО К ОПРИХОДОВАНИЮ: **{calculated_total_pcs} шт.**")
        with col_m2:
            st.markdown(f"🔗 **Будет создана жесткая привязка к карточкам маркетплейсов:**")
            if selected_labels:
                for lbl in selected_labels: st.markdown(f"* `{lbl}`")
            else: st.markdown("*⚠️ Внимание: Этот товар принимается без привязки к магазинам (свободный остаток)*")
            st.info(f"🧾 Будет выставлен счет за логистику прихода: **{total_receipt_cost:.2f} ₽**")

        col_btn1, col_m_btn2 = st.columns(2)
        with col_btn1:
            if st.button("✅ ПОДТВЕРЖДАЮ: ВСЁ ВЕРНО, ЗАПИСАТЬ АКТ", use_container_width=True):
                current_time_stamp = datetime.datetime.now()
                st.session_state.wms_ff_inventory[target_ff_sku] = {
                    'name': ff_name, 'length_cm': c_l, 'width_cm': c_w, 'height_cm': c_h, 'piece_rate': sku_piece_rate,
                    'boxes': st.session_state.wms_ff_inventory.get(target_ff_sku, {}).get('boxes', 0) + input_boxes,
                    'pcs_in_box': input_pcs_in_box,
                    'physical_stock': st.session_state.wms_ff_inventory.get(target_ff_sku, {}).get('physical_stock', 0) + calculated_total_pcs,
                    'fbo_allocated': st.session_state.wms_ff_inventory.get(target_ff_sku, {}).get('fbo_allocated', 0)
                }
                st.session_state.wms_mapping_rules = [r for r in st.session_state.wms_mapping_rules if r['Внутренний артикул ФФ'] != target_ff_sku]
                for label in selected_labels:
                    card_idx = api_options[label]
                    chosen_card = st.session_state.api_pulled_cards[card_idx]
                    st.session_state.wms_mapping_rules.append({"Внутренний артикул ФФ": target_ff_sku, "Магазин": chosen_card['Магазин'], "Артикул продавца": chosen_card['Артикул продавца'], "Баркод": chosen_card['Баркод']})
                st.session_state.wms_receipt_history.append({
                    "Дата операции": current_time_stamp.date(), "Время приемки": current_time_stamp.strftime('%H:%M:%S'), "Внутренний Артикул ФФ": target_ff_sku, 
                    "Разгружено коробов (шт)": input_boxes, "Принято товара (шт)": calculated_total_pcs, "Ставка за шт": sku_piece_rate, "Сумма за разгрузку": cost_unload, "Сумма за обработку": cost_check, "Итого за накладную": total_receipt_cost, "Зафиксированный тариф разгрузки": box_unload_rate_input
                })
                st.session_state.show_confirmation_modal = False
                st.success("🎉 Акт успешно верифицирован!")
                st.rerun()
        with col_m_btn2:
            if st.button("❌ СБРОСИТЬ И ИЗМЕНИТЬ ДАННЫЕ", use_container_width=True):
                st.session_state.show_confirmation_modal = False
                st.rerun()
with tab_stocks:
    st.subheader("📊 Оперативная мультиканальная матрица Единого Стока")
    st.markdown("### 💰 Помагазинная сетка тарифов за сборку FBS")
    st.write("Настройте персональную стоимость обработки 1 заказа для каждого подключенного магазина селлера:")
    
    col_rates_dynamic = st.columns(len(st.session_state.api_pulled_cards))
    for index, card in enumerate(st.session_state.api_pulled_cards):
        with col_rates_dynamic[index]:
            rate_key = f"{card['Магазин']}___{card['Артикул продавца']}"
            current_custom_rate = st.session_state.wms_fbs_custom_rates.get(rate_key, st.session_state.default_fbs_rate)
            new_fbs_rate = st.number_input(f"{card['Артикул продавца']}\n({card['Магазин']})", min_value=0.0, value=float(current_custom_rate), step=5.0, key=f"fbs_input_{rate_key}")
            if new_fbs_rate != current_custom_rate:
                st.session_state.wms_fbs_custom_rates[rate_key] = new_fbs_rate
                st.rerun()
                
    st.write("---")
    rows_unified = []
    total_warehouse_m3 = 0.0
    simulated_fbs_orders_count = 5  
    total_fbs_processing_cost_global = 0.0 
    
    # Словарь для распределения стоимости сборки по магазинам
    fbs_cost_by_shop = {c['Магазин']: 0.0 for c in st.session_state.api_pulled_cards}
    
    for ff_sku, data in st.session_state.wms_ff_inventory.items():
        total_live_fbs_on_marketplaces = 0
        connected_channels_list = []
        for rule in st.session_state.wms_mapping_rules:
            if rule['Внутренний артикул ФФ'] == ff_sku:
                for card in st.session_state.api_pulled_cards:
                    if card['Магазин'] == rule['Магазин'] and card['Артикул продавца'] == rule['Артикул продавца']:
                        mp_stock = int(card.get('Ручной остаток FBS на МП', 0)) 
                        total_live_fbs_on_marketplaces += mp_stock
                        rate_key = f"{card['Магазин']}___{card['Артикул продавца']}"
                        active_fbs_rate = st.session_state.wms_fbs_custom_rates.get(rate_key, st.session_state.default_fbs_rate)
                        
                        if mp_stock > 0: 
                            calc_cost = (simulated_fbs_orders_count * active_fbs_rate)
                            total_fbs_processing_cost_global += calc_cost
                            fbs_cost_by_shop[card['Магазин']] += calc_cost
                            
                        connected_channels_list.append(f"SKU: {rule['Артикул продавца']} | {rule['Магазин']} ({mp_stock} шт. | {active_fbs_rate} ₽/зд)")
        
        phys_stock_on_shelves = max(0, data['physical_stock'] - data['fbo_allocated'] - simulated_fbs_orders_count)
        total_billable_pcs_including_fbs = phys_stock_on_shelves + total_live_fbs_on_marketplaces
        unit_m3 = (data['length_cm'] * data['width_cm'] * data['height_cm']) / 1000000
        total_sku_m3 = unit_m3 * total_billable_pcs_including_fbs
        total_warehouse_m3 += total_sku_m3
        channels_str = ", \n".join(connected_channels_list) if connected_channels_list else "⚠️ Нет привязанных витрин"
        current_sku_rate = data.get('piece_rate', st.session_state.default_piece_rate)
        rows_unified.append({
            "Внутренний Код ФФ": ff_sku, "Описание товара": data['name'], "Габариты упаковки (ЗАМЕР СКЛАДА)": f"{data['length_cm']}x{data['width_cm']}x{data['height_cm']} см",
            "📦 НА ПОЛКАХ (Платное хранение, шт)": total_billable_pcs_including_fbs, "Из них выставлено под FBS менеджером (шт)": total_live_fbs_on_marketplaces, "Уехало на FBO маркетплейсов": data['fbo_allocated'], "Тариф обработки (₽/шт)": f"{current_sku_rate:.2f} ₽", "Детализация связанных витрин селлера": channels_str
        })
        
    if rows_unified:
        df_unified_matrix = pd.DataFrame(rows_unified)
        k1, k2, k3 = st.columns(3)
        with k1: st.metric("Всего позиций ФФ", len(df_unified_matrix))
        with k2: st.metric("Всего штук на платном хранении", int(df_unified_matrix["📦 НА ПОЛКАХ (Платное хранение, шт)"].sum()))
        with k3: st.metric("Активный объем (м³)", f"{total_warehouse_m3:.4f} м³")
        st.write("---")
        st.dataframe(df_unified_matrix, use_container_width=True, hide_index=True)
    else: st.info("👋 Склад полностью пуст. Проведите приемку на первой вкладке.")
with tab_billing:
    st.subheader("📅 Учет дебиторской задолженности и закрытие актов оплат")
    
    # 1. СТРУКТУРНЫЙ ФИЛЬТР ПО МАГАЗИНАМ (КЛИЕНТАМ ФУЛФИЛМЕНТА)
    unique_shops_list = list(set([c['Магазин'] for c in st.session_state.api_pulled_cards]))
    selected_client_filter = st.selectbox("🌐 Фильтрация отчетов по конкретному клиенту (Личному кабинету):", ["Все подключенные кабинеты разом"] + unique_shops_list)
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        custom_range = st.date_input("Выберите интересующий диапазон дат:", value=(st.session_state.start_period, st.session_state.end_period), max_value=today_date, key="calendar_billing")
        if isinstance(custom_range, tuple) and len(custom_range) == 2: st.session_state.start_period, st.session_state.end_period = custom_range
        days_in_period = (st.session_state.end_period - st.session_state.start_period).days + 1
        st.info(f"📆 Выбранный период: **{st.session_state.start_period.strftime('%d.%m.%Y')} — {st.session_state.end_period.strftime('%d.%m.%Y')}** ({days_in_period} дн.)")
    
    with col_b2:
        st.markdown("**💳 Панель закрытия платежей (Менеджер 3PL)**")
        st.write("Вы можете отметить текущий выбранный интервал как полностью оплаченный селлером:")
        
        # Интерактивная кнопка фиксации факта оплаты в Ledger-базу
        if st.button("💳 Отметить этот период как ОПЛАЧЕННЫЙ для выбранного кабинета", use_container_width=True, type="secondary"):
            target_ledger_client = "ALL" if selected_client_filter == "Все подключенные кабинеты разом" else selected_client_filter
            st.session_state.wms_payment_ledger.append({
                "Клиент": target_ledger_client,
                "Старт": st.session_state.start_period,
                "Конец": st.session_state.end_period
            })
            st.success(f"Акт оплаты успешно проведен! Период внесен в архив закрытых платежей.")
            st.rerun()
            
        if st.button("🔄 Сбросить всю историю закрытых оплат (Обнулить долги)", use_container_width=True):
            st.session_state.wms_payment_ledger = []
            st.success("История платежей полностью очищена!")
            st.rerun()

    # ВЫЧИСЛЕНИЕ НАЧИСЛЕНИЙ ЖУРНАЛА ПРИХОДОВ С УЧЕТОМ КЛИЕНТСКОГО ФИЛЬТРА
    df_receipt_history = pd.DataFrame(st.session_state.wms_receipt_history) if st.session_state.wms_receipt_history else pd.DataFrame(columns=["Дата операции", "Время приемки", "Внутренний Артикул ФФ", "Разгружено коробов (шт)", "Принято товара (шт)", "Ставка за шт", "Сумма за разгрузку", "Сумма за обработку", "Итого за накладную"])
    
    total_boxes_unloaded_period = 0
    total_receipt_billing_period = 0.0
    calculated_unload_billing = 0.0
    
    df_receipt_filtered = pd.DataFrame()
    if not df_receipt_history.empty:
        # Сначала фильтруем по датам календаря
        df_receipt_filtered = df_receipt_history[(df_receipt_history['Дата операции'] >= st.session_state.start_period) & (df_receipt_history['Дата операции'] <= st.session_state.end_period)]
        
        # Если выбран конкретный клиент — фильтруем накладные, оставляя только те ФФ-артикулы, которые к нему привязаны
        if selected_client_filter != "Все подключенные кабинеты разом":
            allowed_ff_skus_for_client = [r['Внутренний артикул ФФ'] for r in st.session_state.wms_mapping_rules if r['Магазин'] == selected_client_filter]
            df_receipt_filtered = df_receipt_filtered[df_receipt_filtered['Внутренний Артикул ФФ'].isin(allowed_ff_skus_for_client)]
            
        if not df_receipt_filtered.empty:
            total_boxes_unloaded_period = df_receipt_filtered['Разгружено коробов (шт)'].sum()
            total_receipt_billing_period = df_receipt_filtered['Итого за накладную'].sum()
            calculated_unload_billing = df_receipt_filtered['Сумма за разгрузку'].sum()
            
            st.write("---")
            st.subheader("📋 Срез операционного журнала приходов по выбранному фильтру")
            df_receipt_disp = df_receipt_filtered.copy()
            df_receipt_disp['Дата операции'] = df_receipt_disp['Дата операции'].apply(lambda x: x.strftime('%Y-%m-%d'))
            st.dataframe(df_receipt_disp, use_container_width=True, hide_index=True)

    # ВЫЧИСЛЕНИЕ СТОИМОСТИ ХРАНЕНИЯ И СБОРКИ С УЧЕТОМ СЕЛЛЕРА
    if selected_client_filter != "Все подключенные кабинеты разом":
        client_fbs_cost = fbs_cost_by_shop.get(selected_client_filter, 0.0)
        # Вычисляем долю кубатуры хранения, которую занимает конкретный селлер
        client_m3 = 0.0
        for row in rows_unified:
            if selected_client_filter in row["Детализация связанных витрин селлера"]:
                # Извлекаем кубатуру конкретной позиции
                for ff_sku, data in st.session_state.wms_ff_inventory.items():
                    if ff_sku == row["Внутренний Код ФФ"]:
                        u_m3 = (data['length_cm'] * data['width_cm'] * data['height_cm']) / 1000000
                        client_m3 += (u_m3 * row["📦 НА ПОЛКАХ (Платное хранение, шт)"])
        active_storage_m3_pool = client_m3
        active_fbs_pool = client_fbs_cost
    else:
        active_storage_m3_pool = total_warehouse_m3
        active_fbs_pool = total_fbs_processing_cost_global

    total_storage_cost_period = active_storage_m3_pool * st.session_state.m3_rate * days_in_period
    
    # 2. ПОЛНАЯ ГРЯЗНАЯ СУММА НАЧИСЛЕНИЙ (ДО ВЫЧЕТА ОПЛАТ)
    raw_dirty_total_period = total_storage_cost_period + total_receipt_billing_period + active_fbs_pool

    # --- УМНЫЙ АЛГОРИТМ УЧЕТА CRM-ОПЛАТ (ИСКЛЮЧЕНИЕ ИЗ ОБЩЕГО БАЛАНСА) ---
    paid_already_amount = 0.0
    
    # Проверяем, пересекаются ли даты в календаре с архивом подтвержденных оплат
    for paid_act in st.session_state.wms_payment_ledger:
        if selected_client_filter == "Все подключенные кабинеты разом" or paid_act['Клиент'] == "ALL" or paid_act['Клиент'] == selected_client_filter:
            # Если выбранный в календаре день входит в полностью оплаченный интервал — обнуляем его для счета
            if paid_act['Старт'] <= st.session_state.start_period <= paid_act['Конец'] and paid_act['Старт'] <= st.session_state.end_period <= paid_act['Конец']:
                paid_already_amount = raw_dirty_total_period

    # Итоговый чистый неоплаченный остаток (Красный долг клиента)
    net_unpaid_balance_period = max(0.0, raw_dirty_total_period - paid_already_amount)

    st.write("---")
    st.subheader("🧾 Детализированный 3PL-акт начислений")
    
    billing_period_data = [
        {"Услуга фулфилмента": "Ответственное хранение объема груза на полках (Включая остатки FBS)", "База расчета": f"{active_storage_m3_pool:.4f} м³ × {days_in_period} дн.", "Тарифная ставка": f"{st.session_state.m3_rate:.2f} ₽ за 1 м³ / сутки", "Итого начислено (₽)": f"{total_storage_cost_period:.2f} ₽"},
        {"Услуга фулфилмента": "Сборка, упаковка и маркировка заказов по FBS (Покабинетный обсчет)", "База расчета": "Заказы по кабинету селлера", "Тарифная ставка": "Персональная покабинетная", "Итого начислено (₽)": f"{active_fbs_pool:.2f} ₽"},
        {"Услуга фулфилмента": "Физическая разгрузка коробов (Динамическая в окне приемки)", "База расчета": f"{total_boxes_unloaded_period} кор.", "Тарифная ставка": "Из актов приходов", "Итого начислено (₽)": f"{calculated_unload_billing:.2f} ₽"},
        {"Услуга фулфилмента": "Поартикульная обработка и пересчет груза приемщиком", "База расчета": "Штуки из актов", "Тарифная ставка": "Индивидуальная по SKU", "Итого начислено (₽)": f"{(total_receipt_billing_period - calculated_unload_billing):.2f} ₽"}
    ]
    st.table(pd.DataFrame(billing_period_data))
    
    # Визуализация статуса платежей
    c_m1, c_m2, c_m3 = st.columns(3)
    with c_m1:
        st.metric("Всего начислено за срок", f"{raw_dirty_total_period:.2f} ₽")
    with c_m2:
        st.metric("Уже оплачено клиентом", f"{paid_already_amount:.2f} ₽", delta_color="inverse")
    with c_m3:
        if net_unpaid_balance_period > 0:
            st.metric("🔴 ОСТАТОК К ОПЛАТЕ (НЕОПЛАЧЕННЫЙ ДОЛГ)", f"{net_unpaid_balance_period:.2f} ₽")
        else:
            st.metric("🟢 СТАТУС ПЕРИОДА", "ПОЛНОСТЬЮ ОПЛАЧЕН")
            
    if st.session_state.wms_payment_ledger:
        st.write("📂 **Действующие зафиксированные акты оплат в Ledger-базе фулфилмента:**")
        st.table(pd.DataFrame(st.session_state.wms_payment_ledger))
with tab_rates:
    st.subheader("💰 Управление глобальными базовыми тарифами склада")
    st.session_state.m3_rate = st.number_input("Стоимость хранения 1 м³ груза в сутки (₽):", min_value=0.0, value=float(st.session_state.m3_rate), step=1.0)
    st.session_state.default_fbs_rate = st.number_input("Базовая сборка одного заказа FBS по умолчанию (₽):", min_value=0.0, value=float(st.session_state.default_fbs_rate), step=1.0)
    st.session_state.default_piece_rate = st.number_input("Базовый тариф обработки за 1 шт по умолчанию (₽):", min_value=0.0, value=float(st.session_state.default_piece_rate), step=0.5)

with tab_api:
    st.subheader("🔑 Панель авторизации личных кабинетов")
    input_wb = st.text_input("Введите API Токен WB (тип 'Контент'):", type="password", value=st.session_state.wb_token_saved)
    input_oz_id = st.text_input("Введите Ozon Client-ID:", value=st.session_state.ozon_id_saved)
    input_oz_key = st.text_input("Введите Ozon API Key:", type="password", value=st.session_state.ozon_key_saved)
    if st.button("💾 Активировать интеграцию по API", use_container_width=True):
        st.session_state.wb_token_saved = input_wb
        st.session_state.ozon_id_saved = input_oz_id
        st.session_state.ozon_key_saved = input_oz_key
        st.success("Интеграционные мосты успешно подключены!")
        st.rerun()
