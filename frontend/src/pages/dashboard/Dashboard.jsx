
import { useCallback, useEffect, useMemo, useState } from "react";
import {
    Camera,
    AlertTriangle,
    Activity,
    ShieldCheck,
    Clock,
    RefreshCw,
    Wifi,
    WifiOff,
    TrendingUp,
    Eye,
} from "lucide-react";

import { useHousehold } from "../../contexts/HouseholdContext";
import cameraService from "../../services/cameraService";
import eventService from "../../services/eventService";

function Dashboard() {
    const { householdId, loading: householdLoading } = useHousehold();

    const [cameras, setCameras] = useState([]);
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    // Lấy dữ liệu Dashboard
    const fetchDashboardData = useCallback(async () => {
        if (!householdId) return;

        try {
            setLoading(true);
            setError("");

            const [cameraData, eventData] = await Promise.all([
                cameraService.getAll(householdId),
                eventService.getAll(householdId),
            ]);

            setCameras(cameraData);
            setEvents(eventData);
        } catch (err) {
            console.error("Dashboard error:", err);
            setError(
                err.response?.data?.detail ||
                "Không thể tải dữ liệu Dashboard."
            );
        } finally {
            setLoading(false);
        }
    }, [householdId]);

    useEffect(() => {
        if (householdLoading) return;

        if (!householdId) {
            setCameras([]);
            setEvents([]);
            setLoading(false);
            return;
        }

        fetchDashboardData();
    }, [householdId, householdLoading, fetchDashboardData]);

    // Thống kê camera
    const onlineCameras = cameras.filter(
        (camera) => camera.status?.toLowerCase() === "online"
    ).length;

    const offlineCameras = cameras.length - onlineCameras;

    // Thống kê sự kiện
    const unacknowledgedEvents = events.filter(
        (event) => !event.acknowledged
    );

    const acknowledgedEvents = events.filter(
        (event) => event.acknowledged
    );

    // Sắp xếp sự kiện mới nhất
    const sortedEvents = useMemo(() => {
        return [...events].sort(
            (a, b) =>
                new Date(b.occurred_at) - new Date(a.occurred_at)
        );
    }, [events]);

    const pendingEvents = useMemo(() => {
        return [...unacknowledgedEvents].sort(
            (a, b) =>
                new Date(b.occurred_at) - new Date(a.occurred_at)
        ).slice(0, 5);
    }, [events]);

    const recentEvents = sortedEvents.slice(0, 5);

    // Định dạng thời gian
    const formatDate = (date) => {
        if (!date) return "Không xác định";

        const parsedDate = new Date(date);

        if (Number.isNaN(parsedDate.getTime())) {
            return "Không xác định";
        }

        return parsedDate.toLocaleString("vi-VN");
    };

    // Biểu đồ sự kiện 7 ngày gần nhất
    const chartData = useMemo(() => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        return Array.from({ length: 7 }, (_, index) => {
            const date = new Date(today);
            date.setDate(today.getDate() - (6 - index));

            const nextDate = new Date(date);
            nextDate.setDate(date.getDate() + 1);

            const count = events.filter((event) => {
                if (!event.occurred_at) return false;

                const eventDate = new Date(event.occurred_at);

                return (
                    eventDate >= date &&
                    eventDate < nextDate
                );
            }).length;

            return {
                date,
                label: date.toLocaleDateString("vi-VN", {
                    weekday: "short",
                }),
                dateLabel: date.toLocaleDateString("vi-VN", {
                    day: "2-digit",
                    month: "2-digit",
                }),
                count,
            };
        });
    }, [events]);

    const maxChartValue = Math.max(
        ...chartData.map((item) => item.count),
        1
    );

    const todayEventCount = chartData[6]?.count || 0;

    const statistics = [
        {
            label: "Tổng số camera",
            value: cameras.length,
            description: "Camera đã đăng ký",
            icon: Camera,
            color: "text-blue-600",
            bg: "bg-blue-50",
        },
        {
            label: "Sự kiện té ngã",
            value: events.length,
            description: `${todayEventCount} sự kiện hôm nay`,
            icon: AlertTriangle,
            color: "text-orange-600",
            bg: "bg-orange-50",
        },
        {
            label: "Camera trực tuyến",
            value: onlineCameras,
            description: `${offlineCameras} camera ngoại tuyến`,
            icon: Activity,
            color: "text-emerald-600",
            bg: "bg-emerald-50",
        },
        {
            label: "Chưa xác nhận",
            value: unacknowledgedEvents.length,
            description: "Sự kiện cần được kiểm tra",
            icon: ShieldCheck,
            color: "text-red-600",
            bg: "bg-red-50",
        },
    ];

    if (householdLoading || loading) {
        return (
            <div className="flex min-h-64 items-center justify-center gap-3 text-slate-500">
                <RefreshCw size={20} className="animate-spin" />
                Đang tải dữ liệu Dashboard...
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-xl border border-red-200 bg-red-50 p-5">
                <p className="font-medium text-red-700">{error}</p>

                <button
                    onClick={fetchDashboardData}
                    className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
                >
                    Thử tải lại
                </button>
            </div>
        );
    }

    if (!householdId) {
        return (
            <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center">
                <Camera size={40} className="mx-auto text-slate-300" />
                <h2 className="mt-4 font-semibold text-slate-800">
                    Chưa có hộ gia đình
                </h2>
                <p className="mt-2 text-sm text-slate-500">
                    Hãy tạo hoặc tham gia một hộ gia đình để sử dụng FallGuard.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-6">

            {/* Header */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">
                        Tổng quan
                    </h1>

                    <p className="mt-1 text-sm text-slate-500">
                        Trung tâm giám sát an toàn và hoạt động của gia đình.
                    </p>
                </div>

                <button
                    onClick={fetchDashboardData}
                    disabled={loading}
                    className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
                >
                    <RefreshCw
                        size={16}
                        className={loading ? "animate-spin" : ""}
                    />
                    Làm mới
                </button>
            </div>

            {/* Statistics */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {statistics.map((item) => {
                    const Icon = item.icon;

                    return (
                        <div
                            key={item.label}
                            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                        >
                            <div className="flex items-center justify-between">
                                <p className="text-sm font-medium text-slate-500">
                                    {item.label}
                                </p>

                                <div className={`rounded-xl p-3 ${item.bg}`}>
                                    <Icon size={22} className={item.color} />
                                </div>
                            </div>

                            <p className={`mt-3 text-3xl font-bold ${item.color}`}>
                                {item.value}
                            </p>

                            <p className="mt-2 text-xs text-slate-400">
                                {item.description}
                            </p>
                        </div>
                    );
                })}
            </div>

            {/* Important alerts */}
            <section className="rounded-2xl border border-red-100 bg-white p-5 shadow-sm">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-2">
                        <div className="rounded-lg bg-red-50 p-2">
                            <AlertTriangle size={20} className="text-red-600" />
                        </div>

                        <div>
                            <h2 className="font-semibold text-slate-900">
                                Cảnh báo cần xử lý
                            </h2>
                            <p className="text-xs text-slate-500">
                                Những sự kiện té ngã chưa được xác nhận
                            </p>
                        </div>
                    </div>

                    <span className="w-fit rounded-full bg-red-50 px-3 py-1 text-sm font-semibold text-red-600">
                        {unacknowledgedEvents.length} chưa xác nhận
                    </span>
                </div>

                <div className="mt-5 space-y-3">
                    {pendingEvents.length === 0 ? (
                        <div className="rounded-xl bg-emerald-50 p-5 text-center">
                            <ShieldCheck
                                size={30}
                                className="mx-auto text-emerald-600"
                            />
                            <p className="mt-2 font-medium text-emerald-700">
                                Không có cảnh báo đang chờ xác nhận
                            </p>
                            <p className="mt-1 text-xs text-emerald-600">
                                Tất cả sự kiện hiện tại đã được xác nhận.
                            </p>
                        </div>
                    ) : (
                        pendingEvents.map((event) => (
                            <div
                                key={event.id}
                                className="flex flex-col gap-3 rounded-xl border border-red-100 bg-red-50/40 p-4 sm:flex-row sm:items-center sm:justify-between"
                            >
                                <div className="flex min-w-0 items-start gap-3">
                                    <div className="rounded-lg bg-red-100 p-2">
                                        <AlertTriangle
                                            size={19}
                                            className="text-red-600"
                                        />
                                    </div>

                                    <div className="min-w-0">
                                        <p className="font-semibold text-slate-800">
                                            Phát hiện sự kiện té ngã
                                        </p>

                                        <p className="mt-1 break-all text-xs text-slate-500">
                                            {event.event_id || `Sự kiện #${event.id}`}
                                        </p>

                                        <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
                                            <Clock size={13} />
                                            {formatDate(event.occurred_at)}
                                        </p>
                                    </div>
                                </div>

                                <span className="w-fit shrink-0 rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">
                                    Chưa xác nhận
                                </span>
                            </div>
                        ))
                    )}

                    {unacknowledgedEvents.length > 5 && (
                        <p className="text-center text-xs text-slate-500">
                            Còn {unacknowledgedEvents.length - 5} sự kiện chưa xác nhận khác.
                            Xem trong mục Fall Events.
                        </p>
                    )}
                </div>
            </section>

            {/* Analytics and cameras */}
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">

                {/* Seven-day chart */}
                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="font-semibold text-slate-900">
                                Xu hướng té ngã
                            </h2>
                            <p className="mt-1 text-xs text-slate-500">
                                Thống kê trong 7 ngày gần nhất
                            </p>
                        </div>

                        <div className="rounded-lg bg-blue-50 p-2">
                            <TrendingUp size={21} className="text-blue-600" />
                        </div>
                    </div>

                    <div className="mt-6 flex h-48 items-end justify-around gap-2 border-b border-slate-100 pb-2">
                        {chartData.map((item) => {
                            const barHeight = item.count > 0
                                ? Math.max((item.count / maxChartValue) * 100, 6)
                                : 0;

                            return (
                                <div
                                    key={item.dateLabel}
                                    className="flex h-full flex-1 flex-col items-center justify-end gap-2"
                                >
                                    <span className="text-xs font-semibold text-slate-600">
                                        {item.count > 0 ? item.count : ""}
                                    </span>

                                    <div className="flex h-32 w-full items-end justify-center">
                                        <div
                                            className={`w-full max-w-10 rounded-t-md transition-all ${item.count > 0
                                                    ? "bg-blue-500"
                                                    : "bg-slate-100"
                                                }`}
                                            style={{
                                                height: item.count > 0
                                                    ? `${barHeight}%`
                                                    : "4px",
                                            }}
                                            title={`${item.dateLabel}: ${item.count} sự kiện`}
                                        />
                                    </div>

                                    <div className="text-center">
                                        <p className="text-xs font-medium text-slate-600">
                                            {item.label}
                                        </p>
                                        <p className="mt-1 text-[10px] text-slate-400">
                                            {item.dateLabel}
                                        </p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div className="mt-4 flex items-center justify-between text-sm">
                        <span className="text-slate-500">
                            Tổng sự kiện trong 7 ngày
                        </span>
                        <span className="font-bold text-slate-900">
                            {chartData.reduce((sum, item) => sum + item.count, 0)}
                        </span>
                    </div>
                </section>

                {/* Camera status */}
                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="font-semibold text-slate-900">
                                Thiết bị giám sát
                            </h2>
                            <p className="mt-1 text-xs text-slate-500">
                                Trạng thái camera trong hộ gia đình
                            </p>
                        </div>

                        <div className="rounded-lg bg-slate-100 p-2">
                            <Camera size={21} className="text-slate-600" />
                        </div>
                    </div>

                    <div className="mt-5 space-y-3">
                        {cameras.length === 0 ? (
                            <div className="rounded-xl bg-slate-50 p-6 text-center">
                                <Camera
                                    size={30}
                                    className="mx-auto text-slate-300"
                                />
                                <p className="mt-2 text-sm text-slate-500">
                                    Chưa có camera nào được đăng ký.
                                </p>
                            </div>
                        ) : (
                            cameras.map((camera) => {
                                const isOnline =
                                    camera.status?.toLowerCase() === "online";

                                return (
                                    <div
                                        key={camera.id}
                                        className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-4"
                                    >
                                        <div className="flex min-w-0 items-center gap-3">
                                            <div className={`rounded-lg p-2 ${isOnline
                                                    ? "bg-emerald-50"
                                                    : "bg-red-50"
                                                }`}>
                                                <Camera
                                                    size={20}
                                                    className={
                                                        isOnline
                                                            ? "text-emerald-600"
                                                            : "text-red-500"
                                                    }
                                                />
                                            </div>

                                            <div className="min-w-0">
                                                <p className="truncate text-sm font-semibold text-slate-800">
                                                    {camera.camera_name || "Camera"}
                                                </p>
                                                <p className="mt-1 text-xs text-slate-400">
                                                    {camera.device_id}
                                                </p>
                                            </div>
                                        </div>

                                        <span className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${isOnline
                                                ? "bg-emerald-50 text-emerald-700"
                                                : "bg-red-50 text-red-600"
                                            }`}>
                                            {isOnline ? (
                                                <Wifi size={13} />
                                            ) : (
                                                <WifiOff size={13} />
                                            )}
                                            {isOnline ? "Online" : "Offline"}
                                        </span>
                                    </div>
                                );
                            })
                        )}
                    </div>

                    <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4 text-sm">
                        <span className="text-slate-500">
                            Thiết bị đang trực tuyến
                        </span>
                        <span className="font-semibold text-emerald-600">
                            {onlineCameras}/{cameras.length}
                        </span>
                    </div>
                </section>
            </div>

            {/* Recent activity */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="font-semibold text-slate-900">
                            Hoạt động gần đây
                        </h2>
                        <p className="mt-1 text-xs text-slate-500">
                            5 sự kiện té ngã mới nhất được ghi nhận
                        </p>
                    </div>

                    <Clock size={21} className="text-slate-400" />
                </div>

                <div className="mt-5 overflow-x-auto">
                    {recentEvents.length === 0 ? (
                        <p className="py-8 text-center text-sm text-slate-400">
                            Chưa có sự kiện nào được ghi nhận.
                        </p>
                    ) : (
                        <table className="w-full min-w-[600px] text-left">
                            <thead>
                                <tr className="border-b border-slate-100 text-xs text-slate-500">
                                    <th className="px-3 py-3 font-semibold">
                                        Mã sự kiện
                                    </th>
                                    <th className="px-3 py-3 font-semibold">
                                        Thời gian
                                    </th>
                                    <th className="px-3 py-3 font-semibold">
                                        Trạng thái
                                    </th>
                                </tr>
                            </thead>

                            <tbody>
                                {recentEvents.map((event) => (
                                    <tr
                                        key={event.id}
                                        className="border-b border-slate-50 last:border-0"
                                    >
                                        <td className="max-w-[280px] truncate px-3 py-4 text-sm font-medium text-slate-800">
                                            {event.event_id || `Sự kiện #${event.id}`}
                                        </td>

                                        <td className="px-3 py-4 text-sm text-slate-500">
                                            {formatDate(event.occurred_at)}
                                        </td>

                                        <td className="px-3 py-4">
                                            <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${event.acknowledged
                                                    ? "bg-emerald-50 text-emerald-700"
                                                    : "bg-red-50 text-red-600"
                                                }`}>
                                                {event.acknowledged
                                                    ? "Đã xác nhận"
                                                    : "Chưa xác nhận"}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </section>
        </div>
    );
}

export default Dashboard;
