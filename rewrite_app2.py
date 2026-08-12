import re

with open('app.py', 'r') as f:
    content = f.read()

# Target layout:
# 1. Sidebar is always rendered first, but Broker logic inside sidebar ONLY says "Use main window".
# 2. Main window has Top Header Metrics.
# 3. IF menu_selection != 'Broker': Show Chart Controls, Settings Button, Run Trading Loop.
# 4. IF menu_selection == 'Broker': Show Settings Button, render Broker logic, show system logs.

# --- Extract sidebar exactly ---
sidebar_match = re.search(r'# Sidebar\nwith st\.sidebar:(.*?)(?=\n\n    # Generate the option config dynamically)', content, re.DOTALL)
sidebar_content = sidebar_match.group(0)

# Replace the broker part of sidebar content
search_sidebar_broker = """    if menu_selection == "Broker":
        st.header("Broker Connection")
        broker = st.selectbox("Select Broker", ["Flattrade"])

        config = get_user_config(broker)

        if not st.session_state.logged_in:
            if not config:
                st.warning("Please configure your credentials in the ⚙️ Settings menu first.")
            else:
                st.markdown("---")

                auth_url = f"https://auth.flattrade.in/?app_key={config.api_key}"
                st.markdown(f'<a href="{auth_url}" target="_self"><button style="background-color:#4CAF50; color:white; padding:10px 20px; text-align:center; border:none; border-radius:4px; cursor:pointer; width:100%;">Connect Broker</button></a>', unsafe_allow_html=True)

                query_params = st.query_params
                url_code = query_params.get("code", "")

                if url_code:
                    uid, token = st.session_state.api.generate_session_token(config.api_key, config.api_secret, url_code)
                    if uid and token:
                        if st.session_state.api.login(uid, token):
                            st.session_state.logged_in = True
                            save_session_cache(uid, token)
                            st.success(f"Connected successfully as {uid}!")
                            st.query_params.clear()
                            st.rerun()
                        else:
                            st.error(f"Login validation failed! API Error: {st.session_state.api.last_api_error}")
                    else:
                        st.error(f"Token Generation failed! API Error: {st.session_state.api.last_api_error}")
                        st.query_params.clear()

        else:
            st.success("Broker Connected ✅")
            if st.button("Disconnect Broker"):
                import os
                if os.path.exists(".flattrade_session.json"):
                    os.remove(".flattrade_session.json")
                st.session_state.api = None
                st.session_state.logged_in = False
                st.session_state.running = False
                st.session_state.strategy = None
                st.query_params.clear()
                st.rerun()

    elif menu_selection in ["Practice", "Algo"]:"""

replace_sidebar_broker = """    if menu_selection == "Broker":
        st.info("Broker setup is in the main window.")

    elif menu_selection in ["Practice", "Algo"]:"""

new_sidebar_content = sidebar_content.replace(search_sidebar_broker, replace_sidebar_broker)

# Remove old sidebar from content
content = content.replace(sidebar_content, "")

# Move sidebar to top (before # Chart Controls)
content = content.replace("# Chart Controls (Decoupled from Algo Running state)", new_sidebar_content + "\n\n# Chart Controls (Decoupled from Algo Running state)")

# --- Wrap chart controls ---
chart_controls = """# Chart Controls (Decoupled from Algo Running state)
col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns(5)
with col_c1:
    index_name = st.selectbox("Index", ["NIFTY", "SENSEX"], key="selected_index")

if st.session_state.logged_in:
    if index_name == "NIFTY" and nifty_quote:
        ltp = nifty_quote['lp']
    elif index_name == "SENSEX" and sensex_quote:
        ltp = sensex_quote['lp']

with col_c2:
    opt_type = st.selectbox("Option Type (CE/PE)", ["CE", "PE"])

with col_c3:
    expiry_options = ["Login to fetch expiries"]
    if st.session_state.logged_in and ltp:
        available_expiries = st.session_state.api.get_available_expiries(index_name)
        if available_expiries:
            expiry_options = available_expiries
    expiry_selection = st.selectbox("Expiry", expiry_options)

with col_c4:
    if ltp:
        round_val = 50 if index_name == 'NIFTY' else 100
        atm_strike = round(ltp / round_val) * round_val
        spot_options = []
        for i in range(-20, 21):
            spot_options.append(str(atm_strike + (i * round_val)))

        # Set default to ATM
        default_index = spot_options.index(str(atm_strike))
        strike_selection = st.selectbox("Strike Selection", spot_options, index=default_index)
    else:
        # Fallback if not logged in
        spot_options = ["ATM"]
        for i in range(1, 21):
            spot_options.append(f"ATM +{i}")
            spot_options.append(f"ATM -{i}")
        strike_selection = st.selectbox("Strike Selection", spot_options)

with col_c5:
    chart_interval = st.selectbox("Chart Timeframe", ["1 Min", "3 Min", "5 Min"])
    interval_map = {"1 Min": 1, "3 Min": 3, "5 Min": 5}
    interval_val = interval_map[chart_interval]"""

new_chart_controls = "if menu_selection != 'Broker':\n"
for line in chart_controls.split("\n"):
    new_chart_controls += "    " + line + "\n"
new_chart_controls += "else:\n    interval_val = 1\n    selected_option = None\n"

content = content.replace(chart_controls, new_chart_controls)


# --- Reconstruct Main Area ---
# Provide `render_broker_connection` function definition.

render_func = """def render_broker_connection():
    st.header("Broker Connection")
    broker = st.selectbox("Select Broker", ["Flattrade"])

    config = get_user_config(broker)

    if not st.session_state.logged_in:
        if not config:
            st.warning("Please configure your credentials in the ⚙️ Settings menu first.")
        else:
            st.markdown("---")

            auth_url = f"https://auth.flattrade.in/?app_key={config.api_key}"
            st.markdown(f'<a href="{auth_url}" target="_self"><button style="background-color:#4CAF50; color:white; padding:10px 20px; text-align:center; border:none; border-radius:4px; cursor:pointer; width:100%;">Connect Broker</button></a>', unsafe_allow_html=True)

            query_params = st.query_params
            url_code = query_params.get("code", "")

            if url_code:
                uid, token = st.session_state.api.generate_session_token(config.api_key, config.api_secret, url_code)
                if uid and token:
                    if st.session_state.api.login(uid, token):
                        st.session_state.logged_in = True
                        save_session_cache(uid, token)
                        st.success(f"Connected successfully as {uid}!")
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.error(f"Login validation failed! API Error: {st.session_state.api.last_api_error}")
                else:
                    st.error(f"Token Generation failed! API Error: {st.session_state.api.last_api_error}")
                    st.query_params.clear()

    else:
        st.success("Broker Connected ✅")
        if st.button("Disconnect Broker", key="disconnect_main"):
            import os
            if os.path.exists(".flattrade_session.json"):
                os.remove(".flattrade_session.json")
            st.session_state.api = None
            st.session_state.logged_in = False
            st.session_state.running = False
            st.session_state.strategy = None
            st.query_params.clear()
            st.rerun()

"""

# Insert `render_func` before Settings Button
content = content.replace("# Top right Settings Button", render_func + "\n# Top right Settings Button")

# Replace `run_trading_loop(selected_option)` call at bottom
content = content.replace("\nrun_trading_loop(selected_option)\n", "\nif menu_selection != 'Broker':\n    run_trading_loop(selected_option)\nelse:\n    render_broker_connection()\n")


# Fix system logs conditional rendering (User: "then Broker connection then system logs") - already happening because system logs is at the very bottom.

with open('app.py', 'w') as f:
    f.write(content)
