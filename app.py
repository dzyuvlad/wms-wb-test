import streamlit as st
import pandas as pd
import datetime
import io

# Настройка страницы WMS
st.set_page_config(page_title="WMS Единый Сток OMS", layout="wide", page_icon="📦")

st.title("WMS")
st.write(f"Последняя синхронизация баз данных: `{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`")

# --- ПОЛНОЕ ОБНУЛЕНИЕ ВСЕХ БАЗ ДАННЫХ ДЛЯ ЧИСТОГО ТЕСТА С НУЛЯ ---
if 'wms_ff_inventory' not in st.session_state: st.session_state.wms_ff_inventory = {}
if 'wms_mapping_rules' not in st.session_state: st.session_state.wms_mapping_rules = []
if 'wms_fbs_custom_rates' not in st.session_state: st.session_state.wms_fbs_custom_rates = {}
if 'wms_storage_custom_rates' not in st.session_state: st.session_state.wms_storage_custom_rates = {}
if 'wms_receipt_history' not in st.session_state: st.session_state.wms_receipt_history = []
if 'wms_payment_ledger' not in st.session_state: st.session_state.wms_payment_ledger = [] 
if 'wms_client_groups' not in st.session_state: st.session_state.wms_client_groups = {} 

if 'api_pulled_cards' not in st.session_state:
    st.session_state.api_pulled_cards = [
        {"Магазин": "Wildberries (Кабинет 1)", "Артикул продавца": "001", "Название на витрине": "Сушилка обувная электрическая", "Баркод": "4607123456011", "Ручной остаток FBS на МП": 15, "Актуальный сток FBO на МП": 45},
        {"Магазин": "Wildberries (Кабинет 2)", "Артикул продавца": "WB-SU-DRY", "Название на витрине": "Сушилка для обуви бытовая", "Баркод": "4607123456033", "Ручной остаток FBS на МП": 0, "Актуальный сток FBO на МП": 0},
        {"Магазин": "Ozon (Кабинет 1)", "Артикул продавца": "сушилка1", "Название на витрине": "Электросушилка для сапог", "Баркод": "4607123456022", "Ручной остаток FBS на МП": 20, "Актуальный сток FBO на МП": 80},
        {"Магазин": "Ozon (Кабинет 2)", "Артикул продавца": "OZ-DRY-CLEAN", "Название на витрине": "Сушилка + дезинфектор", "Баркод": "4607123456044", "Ручной остаток FBS на МП": 5, "Актуальный сток FBO на МП": 12},
    ]

today_date = datetime.date.today()
if 'm3_rate' not in st.session_state: st.session_state.m3_rate = 50.0
if 'default_fbs_rate' not in st.session_state: st.session_state.default_fbs_rate = 35.0  
if 'default_piece_rate' not in st.session_state: st.session_state.default_piece_rate = 5.0
if 'wb_token_saved' not in st.session_state: st.session_state.wb_token_saved = ''
if 'ozon_id_saved' not in st.session_state: st.session_state.ozon_id_saved = ''
if 'ozon_key_saved' not in st.session_state: st.session_state.ozon_key_saved = ''
if 'start_period' not in st.session_state: st.session_state.start_period = today_date - datetime.timedelta(days=6)
if 'end_period' not in st.session_state: st.session_state.end_period = today_date

tab_receive, tab_stocks, tab_billing, tab_rates, tab_api = st.tabs([
    "📥 Приемка на баланс ФФ", "📊 Текущие Остатки (Матрица)", "📅 Счета и 3PL-Биллинг", "💰 Управление Тарифами Склада", "🔑 Подключение Ключей API"
])
with tab_receive:
    st.subheader("🌐 Фильтр сессии: Выберите Единого Клиента")
    available_client_groups = list(st.session_state.wms_client_groups.keys())
    
    if not available_client_groups:
        st.warning("⚠️ Сначала создайте хотя бы одного Единого Клиента во вкладке '💰 Управление Тарифами Склада'!")
        selected_client = "Не выбран"
    else:
        selected_client = st.selectbox("С каким клиентом/юрлицом сейчас идет работа:", available_client_groups)

    if selected_client != "Не выбран":
        st.write("---")
        st.subheader("📥 Шаг 1: Выберите товар склада (или зарегистрируйте новый)")
        
        # Фильтруем список внутренних SKU, оставляя только те, что принадлежат текущему клиенту
        client_ff_skus = [ff_sku for ff_sku, data in st.session_state.wms_ff_inventory.items() if data.get('client') == selected_client]
        
        col_step1, col_step2 = st.columns(2)
        with col_step1:
            select_ff = st.selectbox("Выберите внутренний артикул ФФ клиента:", client_ff_skus + ["+ Создать новый ФФ-Артикул"])
            if select_ff == "+ Создать новый ФФ-Артикул":
                target_ff_sku = st.text_input("Присвойте новый код ФФ (Уникальный):", value="ФФ-ТОВАР-01")
                ff_name = st.text_input("Введите название товара для склада:", value="Новинка (Без карточки)")
                c_l = st.number_input("Длина упаковки (см):", min_value=0.1, value=20.0)
                c_w = st.number_input("Ширина упаковки (см):", min_value=0.1, value=15.0)
                c_h = st.number_input("Высота упаковки (см):", min_value=0.1, value=10.0)
                sku_piece_rate = st.number_input("Фиксированный тариф за обработку 1 шт (₽):", min_value=0.0, value=float(st.session_state.default_piece_rate), step=0.5, key="rate_new")
            else:
                target_ff_sku = select_ff
                ff_name = st.session_state.wms_ff_inventory[select_ff]['name']
                c_l = st.number_input("Длина упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['length_cm']))
                c_w = st.number_input("Ширина упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['width_cm']))
                c_h = st.number_input("Высота упаковки (см):", min_value=0.1, value=float(st.session_state.wms_ff_inventory[select_ff]['height_cm']))
                saved_rate = st.session_state.wms_ff_inventory[select_ff].get('piece_rate', st.session_state.default_piece_rate)
                sku_piece_rate = st.number_input("Фиксированный тариф за обработку 1 шт (₽):", min_value=0.0, value=float(saved_rate), step=0.5, key="rate_old")

        with col_step2:
            st.markdown("**🔗 Шаг 2: Привязка карточек маркетплейсов к этому товару**")
            search_query = st.text_input("🔍 Быстрый поиск по артикулу продавца:", value="", placeholder="Например: 001").strip().lower()
            
            # Извлекаем из API-пула только те кабинеты, которые входят в группу выбранного клиента
            allowed_shops = st.session_state.wms_client_groups[selected_client]
            client_api_cards = [c for c in st.session_state.api_pulled_cards if c['Магазин'] in allowed_shops]
            
            api_options = {f"{c['Артикул продавца']} | {c['Название на витрине']} | [{c['Магазин']}]": idx for idx, c in enumerate(st.session_state.api_pulled_cards) if c['Магазин'] in allowed_shops}
            filtered_api_options = {lbl: idx for lbl, idx in api_options.items() if search_query in st.session_state.api_pulled_cards[idx]['Артикул продавца'].lower()} if search_query else api_options

            pre_selected = []
            for rule in st.session_state.wms_mapping_rules:
                if rule['Внутренний артикул ФФ'] == target_ff_sku:
                    for label, idx in api_options.items():
                        card = st.session_state.api_pulled_cards[idx]
                        if card['Магазин'] == rule['Магазин'] and card['Артикул продавца'] == rule['Артикул продавца']: pre_selected.append(label)
            
            selected_labels = st.multiselect("Выберите появившиеся карточки (оставьте пустым, если карточек еще нет):", list(filtered_api_options.keys()), default=[p for p in pre_selected if p in filtered_api_options])
            
            # Кнопка для отложенного связывания ранее принятого пустого товара
            if select_ff != "+ Создать новый ФФ-Артикул":
                if st.button("🔗 Допривязать / Обновить связки Единого Стока", use_container_width=True):
                    st.session_state.wms_mapping_rules = [r for r in st.session_state.wms_mapping_rules if r['Внутренний артикул ФФ'] != target_ff_sku]
                    for label in selected_labels:
                        card_idx = api_options[label]
                        chosen_card = st.session_state.api_pulled_cards[card_idx]
                        st.session_state.wms_mapping_rules.append({"Внутренний артикул ФФ": target_ff_sku, "Магазин": chosen_card['Магазин'], "Артикул продавца": chosen_card['Артикул продавца'], "Баркод": chosen_card['BARCODE' if 'BARCODE' in chosen_card else 'Баркод']})
                    st.success(f"Связки для артикула '{target_ff_sku}' успешно обновлены!")
                    st.rerun()
        if client_ff_skus:
            st.write("---")
            st.markdown("### 🔄 Складское перемещение остатков (Исправление пересорта внутри клиента)")
            col_move1, col_move2, col_move3 = st.columns(3)
            with col_move1: move_ff_target = st.selectbox("1. Выберите исправляемый ФФ-товар:", client_ff_skus, key="move_ff_select")
            current_linked_shops = [r['Магазин'] for r in st.session_state.wms_mapping_rules if r['Внутренний артикул ФФ'] == move_ff_target]
            with col_move2: source_shop_move = st.selectbox("2. С какого ЛК снять остатки:", current_linked_shops if current_linked_shops else ["Нет привязок"])
            with col_move3: destination_shop_move = st.selectbox("3. На какой ЛК перевесить остатки:", [s for s in allowed_shops if s != source_shop_move])
                
            if st.button("🔄 Выполнить внутренний переброс стока", use_container_width=True):
                if source_shop_move == "Нет привязок": st.error("❌ Нечего перемещать!")
                else:
                    for rule in st.session_state.wms_mapping_rules:
                        if rule['Внутренний артикул ФФ'] == move_ff_target and rule['Магазин'] == source_shop_move:
                            for card in st.session_state.api_pulled_cards:
                                if card['Магазин'] == destination_shop_move:
                                    rule['Магазин'], rule['Артикул продавца'], rule['Баркод'] = destination_shop_move, card['Артикул продавца'], card['Баркод']
                                    break
                    st.success("Остатки успешно перемещены!")
                    st.rerun()

        st.write("---")
        st.subheader("📦 Шаг 3: Ввод принятой партии и Контроль кубатуры")
        col_qty1, col_qty2 = st.columns(2)
        with col_qty1:
            input_boxes = st.number_input("Сколько коробов сняли с машины (шт):", min_value=0, value=0, step=1)
            input_pcs_in_box = st.number_input("Сколько штук внутри одного короба:", min_value=1, value=20, step=1)
            box_unload_rate_input = st.number_input("Тариф за физическую разгрузку 1 короба (₽):", min_value=0.0, value=60.0, step=5.0)
        
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
                if calculated_total_pcs <= 0: st.error("❌ Ошибка: Введите количество!")
                else: st.session_state.show_confirmation_modal = True

        if st.session_state.get('show_confirmation_modal', False):
            st.markdown("---")
            st.markdown("### ⚠️ ПОДТВЕРЖДЕНИЕ ПРИЕМКИ")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown(f"📂 **Параметры партии:**\n* Клиент: **{selected_client}**\n* Внутренний код: `{target_ff_sku}` | Товар: **{ff_name}**\n* Коробов: `{input_boxes}`\n## ИТОГО: **{calculated_total_pcs} шт.**")
            with col_m2:
                if selected_labels:
                    for lbl in selected_labels: st.markdown(f"* `{lbl}`")
                else: st.markdown("*⚠️ Карточки еще не созданы (Товар падает в Свободный остаток ФФ)*")
                st.info(f"🧾 Логистика прихода: **{total_receipt_cost:.2f} ₽**")

            col_btn1, col_m_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✅ ПОДТВЕРЖДАЮ: ВСЁ ВЕРНО, ЗАПИСАТЬ АКТ", use_container_width=True):
                    current_time_stamp = datetime.datetime.now()
                    st.session_state.wms_ff_inventory[target_ff_sku] = {
                        'name': ff_name, 'length_cm': c_l, 'width_cm': c_w, 'height_cm': c_h, 'piece_rate': sku_piece_rate, 'client': selected_client,
                        'boxes': st.session_state.wms_ff_inventory.get(target_ff_sku, {}).get('boxes', 0) + input_boxes,
                        'physical_stock': st.session_state.wms_ff_inventory.get(target_ff_sku, {}).get('physical_stock', 0) + calculated_total_pcs, 'fbo_allocated': 0
                    }
                    st.session_state.wms_mapping_rules = [r for r in st.session_state.wms_mapping_rules if r['Внутренний артикул ФФ'] != target_ff_sku]
                    for label in selected_labels:
                        card_idx = api_options[label]
                        chosen_card = st.session_state.api_pulled_cards[card_idx]
                        st.session_state.wms_mapping_rules.append({"Внутренний артикул ФФ": target_ff_sku, "Магазин": chosen_card['Магазин'], "Артикул продавца": chosen_card['Артикул продавца'], "Баркод": chosen_card['Баркод']})
                    st.session_state.wms_receipt_history.append({
                        "Дата операции": current_time_stamp.date(), "Время приемки": current_time_stamp.strftime('%H:%M:%S'), "Внутренний Артикул ФФ": target_ff_sku, 
                        "Разгружено коробов (шт)": input_boxes, "Принято товара (шт)": calculated_total_pcs, "Ставка за шт": sku_piece_rate, "Сумма за разгрузку": cost_unload, "Сумма за обработку": cost_check, "Итого за накладную": total_receipt_cost
                    })
                    st.session_state.show_confirmation_modal = False
                    st.success("🎉 Акт успешно сохранен!")
                    st.rerun()
            with col_m_btn2:
                if st.button("❌ СБРОСИТЬ И ИЗМЕНИТЬ ДАННЫЕ", use_container_width=True):
                    st.session_state.show_confirmation_modal = False
                    st.rerun()
with tab_stocks:
    st.subheader("📊 Оперативная мультиканальная матрица Единого Стока")
    selected_client_group_view = st.selectbox("🌐 Выберите Клиента (Юрлицо) для просмотра остатков:", ["Показать сквозной список всех товаров склада"] + available_client_groups, key="matrix_group_filter")
    st.write("---")
    
    rows_unified = []
    total_warehouse_m3 = 0.0
    simulated_fbs_orders_count = 5  
    total_fbs_processing_cost_global = 0.0 
    fbs_cost_by_shop = {c['Магазин']: 0.0 for c in st.session_state.api_pulled_cards}
    
    allowed_shops_in_view = st.session_state.wms_client_groups[selected_client_group_view] if selected_client_group_view != "Показать сквозной список всех товаров склада" else [c['Магазин'] for c in st.session_state.api_pulled_cards]
        
    for ff_sku, data in st.session_state.wms_ff_inventory.items():
        if selected_client_group_view != "Показать сквозной список всех товаров склада" and data.get('client') != selected_client_group_view:
            continue
            
        total_live_fbs_on_marketplaces = 0
        total_live_fbo_on_marketplaces = 0
        connected_channels_list = []
        
        for rule in st.session_state.wms_mapping_rules:
            if rule['Внутренний артикул ФФ'] == ff_sku:
                for card in st.session_state.api_pulled_cards:
                    if card['Магазин'] == rule['Магазин'] and card['Артикул продавца'] == rule['Артикул продавца']:
                        mp_fbs_stock = int(card.get('Ручной остаток FBS на МП', 0)) 
                        mp_fbo_stock = int(card.get('Актуальный сток FBO на МП', 0)) 
                        total_live_fbs_on_marketplaces += mp_fbs_stock
                        total_live_fbo_on_marketplaces += mp_fbo_stock
                        
                        rate_key = f"{card['Магазин']}___{card['Артикул продавца']}"
                        active_fbs_rate = st.session_state.wms_fbs_custom_rates.get(rate_key, st.session_state.default_fbs_rate)
                        if mp_fbs_stock > 0:
                            calc_cost = (simulated_fbs_orders_count * active_fbs_rate)
                            total_fbs_processing_cost_global += calc_cost
                            fbs_cost_by_shop[card['Магазин']] += calc_cost
                        connected_channels_list.append(f"SKU: {rule['Артикул продавца']} | {rule['Магазин']} (FBS: {mp_fbs_stock} | FBO: {mp_fbo_stock})")
        
        phys_stock_on_shelves = max(0, data['physical_stock'] - data['fbo_allocated'] - simulated_fbs_orders_count)
        total_billable_pcs_including_fbs = phys_stock_on_shelves + total_live_fbs_on_marketplaces
        unit_m3 = (data['length_cm'] * data['width_cm'] * data['height_cm']) / 1000000
        total_sku_m3 = unit_m3 * total_billable_pcs_including_fbs
        total_warehouse_m3 += total_sku_m3
        
        channels_str = ", \n".join(connected_channels_list) if connected_channels_list else "⚠️ Карточки маркетплейсов еще не созданы менеджером"
        current_sku_rate = data.get('piece_rate', st.session_state.default_piece_rate)
        
        rows_unified.append({
            "Внутренний Код ФФ": ff_sku, "Описание товара": data['name'], "Габариты": f"{data['length_cm']}x{data['width_cm']}x{data['height_cm']} см",
            "📦 На складе ФФ (Платное хранение, шт)": phys_stock_on_shelves, "Текущий FBS на МП (шт)": total_live_fbs_on_marketplaces, "Сток FBO на МП (Актуально, шт)": total_live_fbo_on_marketplaces, "Тариф обработки (₽/шт)": f"{current_sku_rate:.2f} ₽", "Детализация связанных витрин селлера": channels_str
        })
        
    if rows_unified:
        df_unified_matrix = pd.DataFrame(rows_unified)
        k1, k2, k3 = st.columns(3)
        with k1: st.metric("Отображено позиций ФФ", len(df_unified_matrix))
        with k2: st.metric("Всего штук на полках ФФ", int(df_unified_matrix["📦 На складе ФФ (Платное хранение, шт)"].sum()))
        with k3: st.metric("Платный объем на полках (м³)", f"{total_warehouse_m3:.4f} м³")
        st.write("---")
        st.dataframe(df_unified_matrix, use_container_width=True, hide_index=True)
    else: st.info("👋 По выбранному фильтру на складе сейчас пусто.")
    raw_dirty_total_period = total_storage_cost_period + total_receipt_billing_period + active_fbs_pool

    paid_already_amount = 0.0
    for paid_act in st.session_state.wms_payment_ledger:
        if selected_client_filter == "Все клиенты разом" or paid_act['Клиент'] == "ALL" or paid_act['Клиент'] == selected_client_filter:
            if paid_act['Старт'] <= st.session_state.start_period <= paid_act['Конец'] and paid_act['Старт'] <= st.session_state.end_period <= paid_act['Конец']:
                paid_already_amount = raw_dirty_total_period

    net_unpaid_balance_period = max(0.0, raw_dirty_total_period - paid_already_amount)

    st.write("---")
    st.subheader("🧾 Детализированный 3PL-акт начислений")
    billing_period_data = [
        {"Услуга фулфилмента": "Ответственное хранение объема груза на полках", "База расчета": f"{active_storage_m3_pool:.4f} м³ средн. за период", "Тарифная ставка": "Персональная покабинетная", "Итого начислено (₽)": f"{total_storage_cost_period:.2f} ₽"},
        {"Услуга фулфилмента": "Сборка, упаковка и маркировка заказов по FBS", "База расчета": "По фактическим заказам ЛК группы", "Тарифная ставка": "Индивидуальная по ЛК", "Итого начислено (₽)": f"{active_fbs_pool:.2f} ₽"},
        {"Услуга фулфилмента": "Физическая разгрузка прибывших коробов (Динамическая)", "База расчета": f"{total_boxes_unloaded_period} - из актов", "Тарифная ставка": "Из актов приходов", "Итого начислено (₽)": f"{calculated_unload_billing:.2f} ₽"},
        {"Услуга фулфилмента": "Поартикульная обработка и пересчет груза", "База расчета": "Штуки из актов", "Тарифная ставка": "Индивидуальная по SKU", "Итого начислено (₽)": f"{(total_receipt_billing_period - calculated_unload_billing):.2f} ₽"}
    ]
    st.table(pd.DataFrame(billing_period_data))
    
    col_metric1, col_metric2, col_metric3 = st.columns(3)
    with col_metric1: st.metric("Всего начислено за срок", f"{raw_dirty_total_period:.2f} ₽")
    with col_metric2: st.metric("Уже оплачено клиентом (Из Ledger-базы)", f"{paid_already_amount:.2f} ₽", delta_color="inverse")
    with col_metric3:
        if net_unpaid_balance_period > 0: st.metric("🔴 ОСТАТОК К ОПЛАТЕ (НЕОПЛАЧЕННЫЙ ДОЛГ КЛИЕНТА)", f"{net_unpaid_balance_period:.2f} ₽")
        else: st.metric("🟢 СТАТУС ПЕРИОДА КЛИЕНТА", "ПОЛНОСТЬЮ ОПЛАЧЕН")
with tab_rates:
    st.subheader("💰 Управление тарифами и группами клиентов фулфилмента")
    
    # БЛОК ОБЪЕДИНЕНИЯ КАБИНЕТОВ МАРКЕТПЛЕЙСОВ В ГРУППЫ КЛИЕНТОВ (ЮРЛИЦА)
    st.markdown("### 🏢 Блок объединения кабинетов маркетплейсов в Группы Клиентов")
    st.write("Создайте единое имя клиента и привяжите к нему технические личные кабинеты маркетплейсов:")
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        new_group_name = st.text_input("Введите имя Единого Клиента / Название Юрлица:", value="ИП Иванов (Бренд Сушилки)")
    with col_g2:
        all_tech_shops = [c['Магазин'] for c in st.session_state.api_pulled_cards]
        selected_shops_for_group = st.multiselect("Выберите магазины, входящие в это юрлицо:", all_tech_shops)
        
    if st.button("➕ Создать / Обновить Группу Клиента", use_container_width=True):
        if not new_group_name.strip(): st.error("❌ Имя клиента не может быть пустым!")
        elif not selected_shops_for_group: st.error("❌ Выберите хотя бы один технический магазин!")
        else:
            st.session_state.wms_client_groups[new_group_name] = selected_shops_for_group
            st.success(f"Клиент '{new_group_name}' успешно зарегистрирован в OMS! Магазины объединены.")
            st.rerun()
            
    if st.session_state.wms_client_groups:
        st.write("📂 **Действующие объединенные Клиенты фулфилмента:**")
        st.write(st.session_state.wms_client_groups)
        
    st.write("---")
    st.markdown("### 🏬 1. Помагазинный тариф ответственного хранения")
    col_storage_dynamic = st.columns(len(st.session_state.api_pulled_cards))
    for index, card in enumerate(st.session_state.api_pulled_cards):
        with col_storage_dynamic[index]:
            shop_key = card['Магазин']
            current_storage_rate = st.session_state.wms_storage_custom_rates.get(shop_key, st.session_state.m3_rate)
            new_storage_rate = st.number_input(f"Хранение 1 м³ (₽/сут):\n[{shop_key}]", min_value=0.0, value=float(current_storage_rate), step=5.0, key=f"storage_tab_input_{shop_key}_{index}")
            if new_storage_rate != current_storage_rate:
                st.session_state.wms_storage_custom_rates[shop_key] = new_storage_rate
                st.rerun()

    st.write("---")
    st.markdown("### 📦 2. Персональная сетка тарифов за сборку FBS")
    col_rates_dynamic = st.columns(len(st.session_state.api_pulled_cards))
    for index, card in enumerate(st.session_state.api_pulled_cards):
        with col_rates_dynamic[index]:
            rate_key = f"{card['Магазин']}___{card['Артикул продавца']}"
            current_custom_rate = st.session_state.wms_fbs_custom_rates.get(rate_key, st.session_state.default_fbs_rate)
            new_fbs_rate = st.number_input(f"Тариф FBS (₽/заказ):\n{card['Артикул продавца']} [{card['Магазин']}]", min_value=0.0, value=float(current_custom_rate), step=5.0, key=f"rates_tab_fbs_{rate_key}")
            if new_fbs_rate != current_custom_rate:
                st.session_state.wms_fbs_custom_rates[rate_key] = new_fbs_rate
                st.rerun()

with tab_api:
    st.subheader("🔑 Панель авторизации личных кабинетов маркетплейсов")
    input_wb = st.text_input("Введите API Токен WB (тип 'Контент'):", type="password", value=st.session_state.wb_token_saved)
    input_oz_id = st.text_input("Введите Ozon Client-ID:", value=st.session_state.ozon_id_saved)
    input_oz_key = st.text_input("Введите Ozon API Key:", type="password", value=st.session_state.ozon_key_saved)
    if st.button("💾 Активировать интеграцию по API", use_container_width=True):
        st.session_state.wb_token_saved, st.session_state.ozon_id_saved, st.session_state.ozon_key_saved = input_wb, input_oz_id, input_oz_key
        st.success("Интеграционные мосты успешно подключены!")
        st.rerun()
