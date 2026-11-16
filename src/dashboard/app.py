import streamlit as st
import pandas as pd

from mqtt_handler import MQTTListener


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Fall Detection Dashboard",
    page_icon="🚨",
    layout="wide"
)


# =====================================================
# MQTT CONNECTION
# =====================================================

@st.cache_resource
def get_mqtt_listener():
    listener = MQTTListener()
    listener.start()
    return listener


listener = get_mqtt_listener()


# =====================================================
# DASHBOARD HEADER
# =====================================================

st.title("🚨 FALL DETECTION MONITORING SYSTEM")

st.caption(
    "Hệ thống giám sát và cảnh báo té ngã "
    "sử dụng YOLO11n, ESP32-CAM và MQTT"
)

st.divider()


# =====================================================
# REAL-TIME DASHBOARD
# =====================================================

@st.fragment(run_every=2)
def render_dashboard():

    connected = listener.is_connected()

    history = listener.get_history()

    latest = listener.get_latest()

    # Nếu ứng dụng vừa khởi động, lấy sự kiện gần nhất
    # đã được lưu trong file lịch sử.
    if latest is None and history:
        latest = history[-1]

    # -------------------------------------------------
    # CONNECTION STATUS
    # -------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:
        if connected:
            st.metric("MQTT Connection", "CONNECTED")
        else:
            st.metric("MQTT Connection", "DISCONNECTED")

    with col2:
        st.metric(
            "Total Fall Events",
            len(history)
        )

    with col3:
        st.metric(
            "Camera",
            latest.get("camera", "N/A") if latest else "N/A"
        )

    st.divider()

    # -------------------------------------------------
    # LATEST EVENT
    # -------------------------------------------------

    st.subheader("📡 Latest Detection Event")

    if latest:

        event = latest.get("event", "UNKNOWN")

        if event == "FALL_DETECTED":
            st.error(
                "🚨 PHÁT HIỆN SỰ KIỆN TÉ NGÃ"
            )
        else:
            st.info(f"Sự kiện: {event}")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Confidence",
                f"{latest.get('average_confidence', 0) * 100:.2f}%"
            )

        with col2:
            st.metric(
                "Fall Duration",
                f"{latest.get('fall_duration_seconds', 0):.2f} giây"
            )

        with col3:
            st.metric(
                "Device ID",
                latest.get("device_id", "N/A")
            )

        st.write(
            "**Camera:**",
            latest.get("camera", "N/A")
        )

        st.write(
            "**Timestamp:**",
            latest.get("timestamp", "N/A")
        )

        with st.expander("Chi tiết Detection"):
            st.json(latest.get("detections", []))

    else:
        st.info(
            "Chưa nhận được sự kiện nào từ camera. "
            "Đang chờ dữ liệu MQTT..."
        )

    st.divider()

    # -------------------------------------------------
    # EVENT HISTORY
    # -------------------------------------------------

    st.subheader("📋 Fall Detection History")

    if history:

        rows = []

        for item in reversed(history):

            rows.append({
                "Timestamp": item.get("timestamp", "N/A"),
                "Device": item.get("device_id", "N/A"),
                "Camera": item.get("camera", "N/A"),
                "Event": item.get("event", "N/A"),
                "Duration (s)": item.get("fall_duration_seconds", 0),
                "Confidence": item.get("average_confidence", 0)
            })

        df = pd.DataFrame(rows)

        df["Timestamp"] = pd.to_datetime(
            df["Timestamp"],
            errors="coerce",
            utc=True
        )

        df["Confidence"] = (
            df["Confidence"] * 100
        ).round(2)

        # --------------------------------------
        # FILTERS
        # --------------------------------------

        st.write("**Bộ lọc sự kiện**")

        col1, col2 = st.columns(2)

        with col1:
            cameras = ["All"] + sorted(
                df["Camera"].dropna().unique().tolist()
            )

            selected_camera = st.selectbox(
                "Camera",
                cameras
            )

        with col2:
            valid_dates = df["Timestamp"].dropna()

            if not valid_dates.empty:
                min_date = valid_dates.min().date()
                max_date = valid_dates.max().date()

                selected_dates = st.date_input(
                    "Khoảng thời gian",
                    value=(min_date, max_date)
                )
            else:
                selected_dates = ()

        # --------------------------------------
        # APPLY FILTERS
        # --------------------------------------

        filtered_df = df.copy()

        if selected_camera != "All":
            filtered_df = filtered_df[
                filtered_df["Camera"] == selected_camera
            ]

        if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
            start_date, end_date = selected_dates

            filtered_df = filtered_df[
                (filtered_df["Timestamp"].dt.date >= start_date) &
                (filtered_df["Timestamp"].dt.date <= end_date)
            ]

        # --------------------------------------
        # DISPLAY FILTERED HISTORY
        # --------------------------------------

        st.write(
            f"Hiển thị {len(filtered_df)} / {len(df)} sự kiện"
        )

        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True
        )

        # --------------------------------------
        # EXPORT FILTERED CSV
        # --------------------------------------

        csv_data = filtered_df.to_csv(
            index=False,
            encoding="utf-8-sig"
        )

        st.download_button(
            label="📥 Export Filtered History to CSV",
            data=csv_data,
            file_name="fall_detection_history.csv",
            mime="text/csv"
        )

        # --------------------------------------
        # CLEAR HISTORY
        # --------------------------------------

        st.divider()

        with st.expander("⚠️ Quản lý dữ liệu lịch sử"):

            st.warning(
                "Xóa lịch sử sẽ xóa toàn bộ sự kiện đã lưu "
                "trong fall_history.json."
            )

            confirm_delete = st.checkbox(
                "Tôi xác nhận muốn xóa toàn bộ lịch sử."
            )

            if st.button(
                "🗑️ Xóa toàn bộ lịch sử",
                type="primary",
                disabled=not confirm_delete
            ):
                listener.clear_history()

                st.success("Đã xóa lịch sử thành công.")

                st.rerun()
    else:
        st.info("Chưa có dữ liệu lịch sử.")

    st.caption(
        "Dashboard tự động cập nhật mỗi 2 giây."
    )


render_dashboard()