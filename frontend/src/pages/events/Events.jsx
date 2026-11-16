
import { useEffect, useState } from "react";
import api from "../../services/api";

import {
    Activity,
    AlertTriangle,
    CheckCircle,
    Clock,
    Eye,
    RefreshCw,
    X,
    Camera,
} from "lucide-react";

import { useHousehold } from "../../contexts/HouseholdContext";
import { eventService } from "../../services/eventService";
import { cameraService } from "../../services/cameraService";
function Events() {
    const { householdId } = useHousehold();

    const [events, setEvents] = useState([]);
    const [cameras, setCameras] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [selectedEvent, setSelectedEvent] = useState(null);
    const [refreshing, setRefreshing] = useState(false);
    const [acknowledging, setAcknowledging] = useState(false);
    const [filter, setFilter] = useState("all");

    const [snapshotUrl, setSnapshotUrl] = useState(null);
    const [snapshotLoading, setSnapshotLoading] = useState(false);
    const [snapshotError, setSnapshotError] = useState("");
    // Statistics
    const totalEvents = events.length;

    const pendingEvents = events.filter(
        (event) => !event.acknowledged
    ).length;

    const acknowledgedEvents = events.filter(
        (event) => event.acknowledged
    ).length;

    // Format date
    const formatDate = (dateString) => {
        if (!dateString) return "--";

        const date = new Date(dateString);

        if (Number.isNaN(date.getTime())) {
            return "--";
        }

        return new Intl.DateTimeFormat("vi-VN", {
            timeZone: "Asia/Ho_Chi_Minh",
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hourCycle: "h23",
        }).format(date);
    };

    // Format confidence
    const formatConfidence = (value) => {
        if (value === null || value === undefined) return "--";

        return `${(Number(value) * 100).toFixed(1)}%`;
    };
    // Fetch events
    const fetchEvents = async () => {
        if (!householdId) {
            setEvents([]);
            setLoading(false);
            return;
        }

        try {
            setError("");

            const data = await eventService.getAll(householdId);

            setEvents(data);
        } catch (err) {
            console.error("Fetch events error:", err);

            setError(
                err.response?.data?.detail ||
                "Không thể tải danh sách sự kiện."
            );
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };
    const fetchCameras = async () => {
        if (!householdId) {
            setCameras([]);
            return;
        }

        try {
            const data = await cameraService.getAll(householdId);
            setCameras(data);
        } catch (err) {
            console.error("Fetch cameras error:", err);
        }
    };
    const fetchSnapshot = async (eventId) => {
        try {
            setSnapshotLoading(true);
            setSnapshotError("");
            setSnapshotUrl(null);

            const response = await api.get(
                `/households/${householdId}/events/${eventId}/snapshot`,
                { responseType: "blob" }
            );

            const imageUrl = URL.createObjectURL(response.data);
            setSnapshotUrl(imageUrl);
        } catch (err) {
            console.error("Fetch snapshot error:", err);
            setSnapshotError(
                err.response?.data?.detail || "Không thể tải ảnh snapshot."
            );
        } finally {
            setSnapshotLoading(false);
        }
    };
    // Load events when household changes
    useEffect(() => {
        setLoading(true);
        fetchEvents();
        fetchCameras();
    }, [householdId]);

    // Refresh
    const handleRefresh = async () => {
        setRefreshing(true);
        await fetchEvents();
    };

    // View event detail
    const handleViewDetail = async (event) => {
        try {
            setError("");
            setSelectedEvent(null);

            if (snapshotUrl) {
                URL.revokeObjectURL(snapshotUrl);
                setSnapshotUrl(null);
            }

            const data = await eventService.getById(
                householdId,
                event.id
            );

            setSelectedEvent(data);

            if (data.snapshot_key) {
                await fetchSnapshot(data.id);
            }
        } catch (err) {
            console.error("Get event detail error:", err);
            setError(
                err.response?.data?.detail ||
                "Không thể tải chi tiết sự kiện."
            );
        }
    };

    // Acknowledge event
    const handleAcknowledge = async (event) => {
        if (event.acknowledged) return;

        try {
            setAcknowledging(true);
            setError("");

            const data = await eventService.acknowledge(
                householdId,
                event.id
            );

            setEvents((previousEvents) =>
                previousEvents.map((item) =>
                    item.id === event.id
                        ? { ...item, acknowledged: true }
                        : item
                )
            );

            if (selectedEvent?.id === event.id) {
                setSelectedEvent((previous) => ({
                    ...previous,
                    ...data,
                    acknowledged: true,
                }));
            }
        } catch (err) {
            console.error("Acknowledge event error:", err);

            setError(
                err.response?.data?.detail ||
                "Không thể xác nhận sự kiện."
            );
        } finally {
            setAcknowledging(false);
        }
    };

    // Filter events
    const filteredEvents = events.filter((event) => {
        if (filter === "pending") {
            return !event.acknowledged;
        }

        if (filter === "acknowledged") {
            return event.acknowledged;
        }

        return true;
    });

    // Sort newest first
    const sortedEvents = [...filteredEvents].sort(
        (a, b) =>
            new Date(b.occurred_at) - new Date(a.occurred_at)
    );
    const getCameraName = (cameraId) => {
        const camera = cameras.find(
            (item) => item.id === cameraId
        );

        return camera?.camera_name || `Camera #${cameraId}`;
    };
    return (
        <div className="space-y-6">

            {/* Page Header */}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">
                        Quản lý sự kiện té ngã
                    </h1>

                    <p className="mt-1 text-sm text-slate-500">
                        Theo dõi và quản lý lịch sử phát hiện té ngã.
                    </p>
                </div>

                <button
                    onClick={handleRefresh}
                    disabled={refreshing}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-600 shadow-sm hover:bg-slate-50 disabled:opacity-50"
                >
                    <RefreshCw
                        size={16}
                        className={refreshing ? "animate-spin" : ""}
                    />

                    Làm mới
                </button>
            </div>

            {/* Error */}
            {error && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                    {error}
                </div>
            )}

            {/* Statistics */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-slate-500">
                                Tổng sự kiện
                            </p>

                            <h3 className="mt-2 text-3xl font-bold text-slate-900">
                                {totalEvents}
                            </h3>
                        </div>

                        <div className="rounded-xl bg-blue-50 p-3 text-blue-600">
                            <Activity size={24} />
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-slate-500">
                                Chưa xác nhận
                            </p>

                            <h3 className="mt-2 text-3xl font-bold text-red-600">
                                {pendingEvents}
                            </h3>
                        </div>

                        <div className="rounded-xl bg-red-50 p-3 text-red-600">
                            <AlertTriangle size={24} />
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-slate-500">
                                Đã xác nhận
                            </p>

                            <h3 className="mt-2 text-3xl font-bold text-green-600">
                                {acknowledgedEvents}
                            </h3>
                        </div>

                        <div className="rounded-xl bg-green-50 p-3 text-green-600">
                            <CheckCircle size={24} />
                        </div>
                    </div>
                </div>

            </div>

            {/* Event List */}
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">

                <div className="flex flex-col gap-4 border-b border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h2 className="font-semibold text-slate-900">
                            Lịch sử sự kiện
                        </h2>

                        <p className="mt-1 text-sm text-slate-500">
                            Danh sách các lần hệ thống phát hiện té ngã.
                        </p>
                    </div>

                    <select
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500"
                    >
                        <option value="all">Tất cả sự kiện</option>
                        <option value="pending">Chưa xác nhận</option>
                        <option value="acknowledged">Đã xác nhận</option>
                    </select>
                </div>

                {loading ? (
                    <div className="p-12 text-center text-sm text-slate-500">
                        Đang tải danh sách sự kiện...
                    </div>
                ) : sortedEvents.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-12 text-center">
                        <Activity size={40} className="text-slate-300" />

                        <p className="mt-4 font-medium text-slate-700">
                            Không có sự kiện nào
                        </p>

                        <p className="mt-1 text-sm text-slate-400">
                            Chưa có dữ liệu phù hợp với bộ lọc.
                        </p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">

                            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                                <tr>
                                    <th className="px-6 py-4">
                                        Mã sự kiện
                                    </th>

                                    <th className="px-6 py-4">
                                        Camera
                                    </th>

                                    <th className="px-6 py-4">
                                        Thời gian
                                    </th>

                                    <th className="px-6 py-4">
                                        Độ tin cậy
                                    </th>

                                    <th className="px-6 py-4">
                                        Trạng thái
                                    </th>

                                    <th className="px-6 py-4 text-right">
                                        Thao tác
                                    </th>
                                </tr>
                            </thead>

                            <tbody className="divide-y divide-slate-100">

                                {sortedEvents.map((event) => (
                                    <tr
                                        key={event.id}
                                        className="hover:bg-slate-50"
                                    >
                                        <td className="px-6 py-4">
                                            <span className="font-medium text-slate-800">
                                                {event.event_id}
                                            </span>
                                        </td>

                                        <td className="px-6 py-4 text-slate-600">
                                            <div>
                                                <p className="text-xs text-slate-500">
                                                    Camera
                                                </p>

                                                <p className="mt-1 font-medium text-slate-800">
                                                    {getCameraName(event.camera_id)}
                                                </p>
                                            </div>
                                        </td>

                                        <td className="px-6 py-4 text-slate-600">
                                            {formatDate(event.occurred_at)}
                                        </td>

                                        <td className="px-6 py-4 text-slate-600">
                                            {formatConfidence(
                                                event.average_confidence
                                            )}
                                        </td>

                                        <td className="px-6 py-4">
                                            {event.acknowledged ? (
                                                <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
                                                    <CheckCircle size={13} />
                                                    Đã xác nhận
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-600">
                                                    <AlertTriangle size={13} />
                                                    Chưa xác nhận
                                                </span>
                                            )}
                                        </td>

                                        <td className="px-6 py-4">
                                            <div className="flex justify-end gap-2">

                                                <button
                                                    onClick={() => handleViewDetail(event)}
                                                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100"
                                                >
                                                    <Eye size={14} />
                                                    Chi tiết
                                                </button>

                                                {!event.acknowledged && (
                                                    <button
                                                        onClick={() => handleAcknowledge(event)}
                                                        disabled={acknowledging}
                                                        className="inline-flex items-center gap-1 rounded-lg bg-green-600 px-3 py-2 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                                                    >
                                                        <CheckCircle size={14} />
                                                        Xác nhận
                                                    </button>
                                                )}

                                            </div>
                                        </td>
                                    </tr>
                                ))}

                            </tbody>
                        </table>
                    </div>
                )}

            </div>


            {/* Event Detail Modal */}
            {selectedEvent && (
                <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 p-4">

                    <div className="my-auto w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl">

                        {/* Header */}
                        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                            <div>
                                <h2 className="text-xl font-bold text-slate-900">
                                    Chi tiết sự kiện
                                </h2>

                                <p className="mt-1 text-sm text-slate-500">
                                    Thông tin phát hiện té ngã từ hệ thống AI
                                </p>
                            </div>

                            <button
                                onClick={() => setSelectedEvent(null)}
                                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Alert */}
                        <div className="mt-5 flex items-center gap-3 rounded-xl border border-red-100 bg-red-50 p-4">
                            <div className="rounded-full bg-red-100 p-3 text-red-600">
                                <AlertTriangle size={24} />
                            </div>

                            <div className="flex-1">
                                <p className="font-semibold text-red-700">
                                    Phát hiện té ngã
                                </p>

                                <p className="mt-1 text-sm text-red-600">
                                    {formatDate(selectedEvent.occurred_at)}
                                </p>
                            </div>

                            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${selectedEvent.acknowledged
                                ? "bg-green-100 text-green-700"
                                : "bg-red-100 text-red-700"
                                }`}>
                                {selectedEvent.acknowledged
                                    ? "Đã xác nhận"
                                    : "Chưa xác nhận"}
                            </span>
                        </div>

                        {/* Detection Information */}
                        <div className="mt-6">
                            <h3 className="font-semibold text-slate-900">
                                Thông tin phát hiện
                            </h3>

                            <div className="mt-3 grid grid-cols-2 gap-3">

                                <div className="rounded-xl bg-slate-50 p-4">
                                    <p className="text-xs text-slate-500">
                                        Camera
                                    </p>

                                    <p className="mt-2 font-semibold text-slate-800">
                                        {getCameraName(selectedEvent.camera_id)}
                                    </p>
                                </div>

                                <div className="rounded-xl bg-slate-50 p-4">
                                    <p className="text-xs text-slate-500">
                                        Thời lượng té ngã
                                    </p>

                                    <p className="mt-2 font-semibold text-slate-800">
                                        {selectedEvent.fall_duration_seconds != null
                                            ? `${Number(selectedEvent.fall_duration_seconds).toFixed(2)} giây`
                                            : "--"}
                                    </p>
                                </div>

                                <div className="rounded-xl bg-slate-50 p-4">
                                    <p className="text-xs text-slate-500">
                                        Độ tin cậy AI
                                    </p>

                                    <p className="mt-2 font-semibold text-blue-600">
                                        {formatConfidence(selectedEvent.average_confidence)}
                                    </p>
                                </div>

                                <div className="rounded-xl bg-slate-50 p-4">
                                    <p className="text-xs text-slate-500">
                                        Thời điểm ghi nhận
                                    </p>

                                    <p className="mt-2 font-semibold text-slate-800">
                                        {formatDate(selectedEvent.created_at)}
                                    </p>
                                </div>

                            </div>
                        </div>

                        {/* Processing Status */}
                        <div className="mt-6">
                            <h3 className="font-semibold text-slate-900">
                                Trạng thái xử lý
                            </h3>
                            {/* Event Snapshot */}
                            {/* Event Snapshot */}
                            <div className="mt-6">
                                <h3 className="font-semibold text-slate-900">
                                    Ảnh tại thời điểm phát hiện
                                </h3>

                                <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-slate-50 p-4">
                                    {snapshotLoading ? (
                                        <div className="flex flex-col items-center py-8">
                                            <RefreshCw className="animate-spin text-blue-500" size={30} />
                                            <p className="mt-3 text-sm text-slate-500">
                                                Đang tải ảnh...
                                            </p>
                                        </div>
                                    ) : snapshotUrl ? (
                                        <img
                                            src={snapshotUrl}
                                            alt="Ảnh tại thời điểm phát hiện té ngã"
                                            className="mx-auto max-h-[400px] w-full rounded-lg object-contain"
                                        />
                                    ) : snapshotError ? (
                                        <div className="py-8 text-center">
                                            <Camera size={36} className="mx-auto text-slate-300" />
                                            <p className="mt-3 text-sm text-red-500">
                                                {snapshotError}
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col items-center py-8 text-center">
                                            <Camera size={36} className="text-slate-300" />
                                            <p className="mt-3 text-sm font-medium text-slate-600">
                                                Chưa có ảnh sự kiện
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>
                            <div className="mt-3 flex items-center gap-3 rounded-xl border border-slate-200 p-4">
                                {selectedEvent.acknowledged ? (
                                    <CheckCircle className="text-green-600" size={22} />
                                ) : (
                                    <Clock className="text-orange-500" size={22} />
                                )}

                                <div>
                                    <p className="text-sm font-semibold text-slate-800">
                                        {selectedEvent.acknowledged
                                            ? "Sự kiện đã được xác nhận"
                                            : "Sự kiện đang chờ xác nhận"}
                                    </p>

                                    <p className="mt-1 text-xs text-slate-500">
                                        {selectedEvent.acknowledged
                                            ? "Người dùng đã xác nhận sự kiện."
                                            : "Vui lòng kiểm tra tình trạng người được giám sát."}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Event ID */}
                        <div className="mt-6">
                            <p className="text-xs text-slate-500">
                                Mã sự kiện
                            </p>

                            <p className="mt-1 break-all rounded-lg bg-slate-50 p-3 font-mono text-xs text-slate-600">
                                {selectedEvent.event_id}
                            </p>
                        </div>

                        {/* Actions */}
                        <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-4">

                            <button
                                onClick={() => {
                                    setSelectedEvent(null);

                                    if (snapshotUrl) {
                                        URL.revokeObjectURL(snapshotUrl);
                                        setSnapshotUrl(null);
                                    }

                                    setSnapshotError("");
                                }}
                                className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                            >
                                Đóng
                            </button>

                            {!selectedEvent.acknowledged && (
                                <button
                                    onClick={() => handleAcknowledge(selectedEvent)}
                                    disabled={acknowledging}
                                    className="rounded-xl bg-green-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                                >
                                    {acknowledging
                                        ? "Đang xử lý..."
                                        : "Xác nhận đã xử lý"}
                                </button>
                            )}

                        </div>

                    </div>
                </div>
            )}


        </div>
    );
}

export default Events;
