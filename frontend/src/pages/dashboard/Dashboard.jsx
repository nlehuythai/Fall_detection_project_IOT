import { useEffect, useState } from "react";
import {
    Camera,
    AlertTriangle,
    Activity,
    ShieldCheck,
    Clock,
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

    useEffect(() => {
        if (householdLoading) return;

        if (!householdId) {
            setLoading(false);
            return;
        }

        const fetchDashboardData = async () => {
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
        };

        fetchDashboardData();
    }, [householdId, householdLoading]);

    const onlineCameras = cameras.filter(
        (camera) => camera.status === "online"
    ).length;

    const unacknowledgedEvents = events.filter(
        (event) => !event.acknowledged
    ).length;

    const statistics = [
        {
            label: "Tổng số camera",
            value: cameras.length,
            description: "Camera đã đăng ký",
            icon: Camera,
        },
        {
            label: "Sự kiện té ngã",
            value: events.length,
            description: "Tổng số sự kiện được ghi nhận",
            icon: AlertTriangle,
        },
        {
            label: "Camera trực tuyến",
            value: onlineCameras,
            description: "Thiết bị đang kết nối",
            icon: Activity,
        },
        {
            label: "Chưa xác nhận",
            value: unacknowledgedEvents,
            description: "Sự kiện cần được kiểm tra",
            icon: ShieldCheck,
        },
    ];

    const recentEvents = [...events]
        .sort(
            (a, b) =>
                new Date(b.occurred_at) - new Date(a.occurred_at)
        )
        .slice(0, 5);

    const formatDate = (date) => {
        if (!date) return "Không xác định";

        return new Date(date).toLocaleString("vi-VN");
    };

    if (householdLoading || loading) {
        return (
            <div className="p-8 text-center text-slate-500">
                Đang tải dữ liệu...
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-600">
                {error}
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-slate-900">
                    Tổng quan
                </h1>
                <p className="mt-1 text-sm text-slate-500">
                    Theo dõi tình trạng an toàn và hoạt động của hệ thống.
                </p>
            </div>

            {/* Statistics */}
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
                {statistics.map((item) => {
                    const Icon = item.icon;

                    return (
                        <div
                            key={item.label}
                            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
                        >
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-slate-500">
                                        {item.label}
                                    </p>

                                    <p className="mt-3 text-3xl font-bold text-slate-900">
                                        {item.value}
                                    </p>
                                </div>

                                <div className="rounded-xl bg-slate-100 p-3">
                                    <Icon size={24} className="text-slate-700" />
                                </div>
                            </div>

                            <p className="mt-4 text-xs text-slate-400">
                                {item.description}
                            </p>
                        </div>
                    );
                })}
            </div>

            {/* System status and recent events */}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">

                <div className="rounded-2xl border border-slate-200 bg-white p-6">
                    <div className="flex items-center justify-between">
                        <h2 className="font-semibold text-slate-900">
                            Trạng thái hệ thống
                        </h2>

                        <ShieldCheck
                            className="text-emerald-500"
                            size={22}
                        />
                    </div>

                    <div className="mt-6 space-y-5">
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-600">
                                Camera trực tuyến
                            </span>

                            <span className="text-sm font-semibold text-emerald-600">
                                {onlineCameras}/{cameras.length}
                            </span>
                        </div>

                        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                            <div
                                className="h-full rounded-full bg-emerald-500"
                                style={{
                                    width: `${cameras.length
                                            ? (onlineCameras / cameras.length) * 100
                                            : 0
                                        }%`,
                                }}
                            />
                        </div>

                        <div className="flex items-center justify-between">
                            <span className="text-sm text-slate-600">
                                Sự kiện chưa xác nhận
                            </span>

                            <span className="text-sm font-semibold text-red-600">
                                {unacknowledgedEvents}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-6">
                    <div className="flex items-center justify-between">
                        <h2 className="font-semibold text-slate-900">
                            Hoạt động gần đây
                        </h2>

                        <Clock className="text-slate-400" size={22} />
                    </div>

                    <div className="mt-6 space-y-4">
                        {recentEvents.length === 0 ? (
                            <p className="text-center text-sm text-slate-400">
                                Chưa có sự kiện nào được ghi nhận.
                            </p>
                        ) : (
                            recentEvents.map((event) => (
                                <div
                                    key={event.id}
                                    className="flex items-start gap-3 border-b border-slate-100 pb-4 last:border-0"
                                >
                                    <div className="rounded-lg bg-red-50 p-2">
                                        <AlertTriangle
                                            size={18}
                                            className="text-red-500"
                                        />
                                    </div>

                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-medium text-slate-800">
                                            Phát hiện sự kiện té ngã
                                        </p>

                                        <p className="mt-1 text-xs text-slate-400">
                                            {event.event_id}
                                        </p>

                                        <p className="mt-1 text-xs text-slate-400">
                                            {formatDate(event.occurred_at)}
                                        </p>
                                    </div>

                                    <span
                                        className={`shrink-0 rounded-full px-2 py-1 text-xs font-medium ${event.acknowledged
                                                ? "bg-emerald-50 text-emerald-600"
                                                : "bg-red-50 text-red-600"
                                            }`}
                                    >
                                        {event.acknowledged
                                            ? "Đã xác nhận"
                                            : "Chưa xác nhận"}
                                    </span>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Dashboard;