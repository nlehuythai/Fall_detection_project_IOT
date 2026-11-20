
import { useEffect, useState } from "react";
import {
    Camera,
    Plus,
    RefreshCw,
    Pencil,
    Trash2,
    Wifi,
    WifiOff,
    X,
    Copy,
    Check,
    Eye,
    Play,
    Square,
} from "lucide-react";

import { useHousehold } from "../../contexts/HouseholdContext";
import cameraService from "../../services/cameraService";
import LiveView from "../../components/LiveView";
function Cameras() {
    const { householdId, loading: householdLoading } = useHousehold();

    const [cameras, setCameras] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const [showAddModal, setShowAddModal] = useState(false);
    const [deviceId, setDeviceId] = useState("");
    const [cameraName, setCameraName] = useState("");
    const [streamUrl, setStreamUrl] = useState("");
    const [viewingCamera, setViewingCamera] = useState(null);
    const [streamStatus, setStreamStatus] = useState("idle");
    const [streamReloadKey, setStreamReloadKey] = useState(0);
    const [submitting, setSubmitting] = useState(false);
    const [createdCamera, setCreatedCamera] = useState(null);
    const [copied, setCopied] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);

    const [editingCamera, setEditingCamera] = useState(null);
    const [editDeviceId, setEditDeviceId] = useState("");
    const [editCameraName, setEditCameraName] = useState("");
    const [editStreamUrl, setEditStreamUrl] = useState("");
    const [updating, setUpdating] = useState(false);
    const [monitoringCameraId, setMonitoringCameraId] = useState(null);
    const fetchCameras = async () => {
        if (!householdId) {
            setCameras([]);
            setLoading(false);
            return;
        }

        try {
            setLoading(true);
            setError("");

            const data = await cameraService.getAll(householdId);
            setCameras(data);
        } catch (err) {
            console.error("Camera error:", err);
            setError(
                err.response?.data?.detail ||
                "Không thể tải danh sách camera."
            );
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!householdLoading) {
            fetchCameras();
        }
    }, [householdId, householdLoading]);

    const onlineCount = cameras.filter(
        (camera) => camera.status === "online"
    ).length;

    const offlineCount = cameras.length - onlineCount;

    if (householdLoading || loading) {
        return (
            <div className="p-8 text-center text-slate-500">
                Đang tải danh sách camera...
            </div>
        );
    }
    const handleAddCamera = async (e) => {
        e.preventDefault();

        if (!deviceId.trim() || !cameraName.trim()) {
            setError("Vui lòng nhập đầy đủ thông tin.");
            return;
        }

        try {
            setSubmitting(true);
            setError("");

            const data = await cameraService.create(householdId, {
                device_id: deviceId.trim(),
                camera_name: cameraName.trim(),
                stream_url: streamUrl.trim() || null,
            });

            setCreatedCamera(data);
            setDeviceId("");
            setCameraName("");
            setStreamUrl("");
            await fetchCameras();
        } catch (err) {
            console.error("Create camera error:", err);

            setError(
                err.response?.data?.detail ||
                "Không thể đăng ký camera."
            );
        } finally {
            setSubmitting(false);
        }
    };
    const handleCopyKey = async () => {
        if (!createdCamera?.device_api_key) return;

        await navigator.clipboard.writeText(
            createdCamera.device_api_key
        );

        setCopied(true);
    };
    const openEditModal = (camera) => {
        setEditingCamera(camera);
        setEditDeviceId(camera.device_id);
        setEditCameraName(camera.camera_name);
        setEditStreamUrl(camera.stream_url || "");
        setShowEditModal(true);
        setError("");
    };

    const handleUpdateCamera = async (e) => {
        e.preventDefault();

        if (!editingCamera) return;

        try {
            setUpdating(true);
            setError("");

            await cameraService.update(
                householdId,
                editingCamera.id,
                {
                    device_id: editDeviceId.trim(),
                    camera_name: editCameraName.trim(),
                    stream_url: editStreamUrl.trim() || null,
                }
            );

            setShowEditModal(false);
            setEditingCamera(null);

            await fetchCameras();
        } catch (err) {
            console.error("Update camera error:", err);

            setError(
                err.response?.data?.detail ||
                "Không thể cập nhật camera."
            );
        } finally {
            setUpdating(false);
        }
    };
    const handleDeleteCamera = async (camera) => {
        const confirmed = window.confirm(
            `Bạn có chắc chắn muốn xóa camera "${camera.camera_name}" không?`
        );

        if (!confirmed) return;

        try {
            setError("");

            await cameraService.delete(
                householdId,
                camera.id
            );

            await fetchCameras();
        } catch (err) {
            console.error("Delete camera error:", err);

            setError(
                err.response?.data?.detail ||
                "Không thể xóa camera."
            );
        }
    };
    const handleToggleMonitoring = async (camera) => {
        const isMonitoring = camera.monitoring_enabled;

        const confirmed = window.confirm(
            isMonitoring
                ? `Bạn có chắc chắn muốn tắt giám sát camera "${camera.camera_name}" không?`
                : `Bạn có chắc chắn muốn bật giám sát camera "${camera.camera_name}" không?`
        );

        if (!confirmed) return;

        try {
            setError("");
            setMonitoringCameraId(camera.id);

            if (isMonitoring) {
                await cameraService.stopMonitoring(
                    householdId,
                    camera.id
                );
            } else {
                await cameraService.startMonitoring(
                    householdId,
                    camera.id
                );
            }

            await fetchCameras();

        } catch (err) {
            console.error("Toggle monitoring error:", err);

            setError(
                err.response?.data?.detail ||
                "Không thể thay đổi trạng thái giám sát camera."
            );

        } finally {
            setMonitoringCameraId(null);
        }
    };
    // Mở luồng video
    const openLiveCamera = (camera) => {
        setStreamStatus("connecting");
        setStreamReloadKey((prev) => prev + 1);
        setViewingCamera(camera);
    };

    // Tải lại luồng video
    const reloadStream = () => {
        setStreamStatus("connecting");
        setStreamReloadKey((prev) => prev + 1);
    };

    const closeLiveCamera = () => {
        setViewingCamera(null);
        setStreamStatus("idle");
    };
    return (
        <div className="space-y-6">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                    <div className="flex items-center gap-3">
                        <Camera className="text-blue-600" size={28} />
                        <h1 className="text-2xl font-bold text-slate-900">
                            Quản lý camera
                        </h1>
                    </div>

                    <p className="mt-2 text-sm text-slate-500">
                        Quản lý các thiết bị giám sát trong hộ gia đình.
                    </p>
                </div>

                <button
                    onClick={fetchCameras}
                    className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                    <RefreshCw size={16} />
                    Làm mới
                </button>
            </div>
            <button
                onClick={() => {
                    setCreatedCamera(null);
                    setShowAddModal(true);
                }}
                className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
            >
                <Plus size={18} />
                Thêm camera
            </button>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <p className="text-sm text-slate-500">Tổng camera</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">
                        {cameras.length}
                    </p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <p className="text-sm text-slate-500">Đang trực tuyến</p>
                    <p className="mt-2 text-2xl font-bold text-emerald-600">
                        {onlineCount}
                    </p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <p className="text-sm text-slate-500">Ngoại tuyến</p>
                    <p className="mt-2 text-2xl font-bold text-red-500">
                        {offlineCount}
                    </p>
                </div>
            </div>

            {error && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                    {error}
                </div>
            )}

            {!householdId ? (
                <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center">
                    <Camera className="mx-auto text-slate-300" size={40} />
                    <p className="mt-3 font-medium text-slate-700">
                        Bạn chưa có hộ gia đình.
                    </p>
                </div>
            ) : cameras.length === 0 ? (
                <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center">
                    <Camera className="mx-auto text-slate-300" size={40} />
                    <p className="mt-3 font-medium text-slate-700">
                        Chưa có camera nào.
                    </p>
                    <p className="mt-1 text-sm text-slate-400">
                        Danh sách camera sẽ hiển thị tại đây sau khi được đăng ký.
                    </p>
                </div>
            ) : (
                <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-slate-50 text-slate-500">
                                <tr>
                                    <th className="px-6 py-4 font-medium">Tên camera</th>
                                    <th className="px-6 py-4 font-medium">Mã thiết bị</th>
                                    <th className="px-6 py-4 font-medium">Trạng thái</th>
                                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                                        Giám sát
                                    </th>
                                    <th className="px-6 py-4 text-right font-medium">
                                        Thao tác
                                    </th>
                                </tr>
                            </thead>

                            <tbody className="divide-y divide-slate-100">
                                {cameras.map((camera) => (
                                    <tr key={camera.id} className="hover:bg-slate-50">
                                        <td className="px-6 py-4 font-medium text-slate-800">
                                            {camera.camera_name}
                                        </td>

                                        <td className="px-6 py-4 text-slate-500">
                                            {camera.device_id}
                                        </td>

                                        <td className="px-6 py-4">
                                            {camera.status === "online" ? (
                                                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-600">
                                                    <Wifi size={14} />
                                                    Trực tuyến
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-600">
                                                    <WifiOff size={14} />
                                                    Ngoại tuyến
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {camera.monitoring_enabled ? (
                                                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-600">
                                                    <Play size={12} />
                                                    Đang bật
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
                                                    <Square size={12} />
                                                    Đang tắt
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                <button
                                                    onClick={() => handleToggleMonitoring(camera)}
                                                    disabled={monitoringCameraId === camera.id}
                                                    className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50 ${camera.monitoring_enabled
                                                        ? "border-red-200 text-red-600 hover:bg-red-50"
                                                        : "border-emerald-200 text-emerald-600 hover:bg-emerald-50"
                                                        }`}
                                                >
                                                    {monitoringCameraId === camera.id ? (
                                                        <RefreshCw size={14} className="animate-spin" />
                                                    ) : camera.monitoring_enabled ? (
                                                        <Square size={14} />
                                                    ) : (
                                                        <Play size={14} />
                                                    )}

                                                    {monitoringCameraId === camera.id
                                                        ? "Đang xử lý..."
                                                        : camera.monitoring_enabled
                                                            ? "Tắt giám sát"
                                                            : "Bật giám sát"}
                                                </button>
                                                <button
                                                    onClick={() => openLiveCamera(camera)}
                                                    disabled={!camera.stream_url}
                                                    className="inline-flex items-center gap-2 rounded-lg border border-blue-200 px-3 py-2 text-xs font-medium text-blue-600 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
                                                >
                                                    <Eye size={14} />
                                                    Xem trực tiếp
                                                </button>
                                                <button
                                                    onClick={() => openEditModal(camera)}
                                                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100"
                                                >
                                                    <Pencil size={14} />
                                                    Chỉnh sửa
                                                </button>

                                                <button
                                                    onClick={() => handleDeleteCamera(camera)}
                                                    className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-50"
                                                >
                                                    <Trash2 size={14} />
                                                    Xóa
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
            {/* Live Camera Modal */}
            {viewingCamera && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
                    <div className="w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-xl">

                        {/* Header */}
                        <div className="flex items-center justify-between border-b border-slate-200 p-5">
                            <div>
                                <h2 className="text-lg font-bold text-slate-900">
                                    {viewingCamera.camera_name}
                                </h2>

                                <p className="mt-1 text-xs text-slate-500">
                                    {viewingCamera.device_id}
                                </p>
                            </div>

                            <button
                                onClick={closeLiveCamera}
                                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Video */}
                        <div className="relative bg-black p-2">
                            <LiveView
                                householdId={householdId}
                                cameraId={viewingCamera.id}
                                reloadKey={streamReloadKey}
                                onStatusChange={setStreamStatus}
                            />

                            {streamStatus === "connecting" && (
                                <div className="absolute inset-0 flex items-center justify-center bg-black/70">
                                    <p className="text-sm text-white">
                                        Đang kết nối camera...
                                    </p>
                                </div>
                            )}

                            {streamStatus === "error" && (
                                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/80">
                                    <WifiOff size={32} className="text-red-400" />
                                    <p className="text-sm text-white">
                                        Không thể nhận luồng video
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="flex items-center justify-between p-4">
                            <p className="text-xs text-slate-500">
                                Luồng video ESP32-CAM
                            </p>

                            <div className="flex items-center gap-2">
                                <button
                                    onClick={reloadStream}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                                >
                                    <RefreshCw size={15} />
                                    Tải lại luồng
                                </button>

                                <button
                                    onClick={closeLiveCamera}
                                    className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
                                >
                                    Đóng
                                </button>
                            </div>
                        </div>

                    </div>
                </div>
            )}
            {/* Add Camera Modal */}
            {showAddModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
                    <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">

                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-bold text-slate-900">
                                {createdCamera
                                    ? "Đăng ký camera thành công"
                                    : "Thêm camera mới"}
                            </h2>

                            <button
                                onClick={() => {
                                    setShowAddModal(false);
                                    setCreatedCamera(null);
                                    setCopied(false);
                                    setError("");
                                }}
                                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {!createdCamera ? (
                            <form
                                onSubmit={handleAddCamera}
                                className="mt-6 space-y-5"
                            >
                                <div>
                                    <label className="mb-2 block text-sm font-medium text-slate-700">
                                        Mã thiết bị
                                    </label>

                                    <input
                                        type="text"
                                        value={deviceId}
                                        onChange={(e) =>
                                            setDeviceId(e.target.value)
                                        }
                                        placeholder="Ví dụ: CAMERA_02"
                                        maxLength={100}
                                        required
                                        className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                                    />

                                    <p className="mt-1 text-xs text-slate-400">
                                        Mã định danh duy nhất của thiết bị.
                                    </p>
                                </div>

                                <div>
                                    <label className="mb-2 block text-sm font-medium text-slate-700">
                                        Tên camera
                                    </label>

                                    <input
                                        type="text"
                                        value={cameraName}
                                        onChange={(e) =>
                                            setCameraName(e.target.value)
                                        }
                                        placeholder="Ví dụ: Camera phòng khách"
                                        minLength={2}
                                        maxLength={150}
                                        required
                                        className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                                    />
                                </div>
                                <div>
                                    <label className="mb-2 block text-sm font-medium text-slate-700">
                                        Địa chỉ luồng video (Stream URL)
                                    </label>

                                    <input
                                        type="url"
                                        value={streamUrl}
                                        onChange={(e) => setStreamUrl(e.target.value)}
                                        placeholder="http://192.168.1.106:81/stream"
                                        maxLength={500}
                                        className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                                    />

                                    <p className="mt-1 text-xs text-slate-400">
                                        Địa chỉ video trực tiếp từ ESP32-CAM. Có thể để trống nếu chưa cấu hình.
                                    </p>
                                </div>

                                {error && (
                                    <p className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
                                        {error}
                                    </p>
                                )}

                                <div className="flex justify-end gap-3 pt-2">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setShowAddModal(false);
                                            setError("");
                                        }}
                                        className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                                    >
                                        Hủy
                                    </button>

                                    <button
                                        type="submit"
                                        disabled={submitting}
                                        className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                                    >
                                        {submitting
                                            ? "Đang đăng ký..."
                                            : "Đăng ký camera"}
                                    </button>
                                </div>
                            </form>
                        ) : (
                            <div className="mt-6 space-y-5">
                                <div className="rounded-xl bg-emerald-50 p-4">
                                    <p className="font-medium text-emerald-700">
                                        Camera đã được đăng ký thành công!
                                    </p>

                                    <p className="mt-1 text-sm text-emerald-600">
                                        {createdCamera.camera_name}
                                    </p>
                                </div>

                                <div>
                                    <label className="mb-2 block text-sm font-medium text-slate-700">
                                        Device API Key
                                    </label>

                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            readOnly
                                            value={createdCamera.device_api_key}
                                            className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs"
                                        />

                                        <button
                                            onClick={handleCopyKey}
                                            className="flex items-center gap-2 rounded-xl bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700"
                                        >
                                            {copied ? (
                                                <Check size={16} />
                                            ) : (
                                                <Copy size={16} />
                                            )}

                                            {copied ? "Đã sao chép" : "Sao chép"}
                                        </button>
                                    </div>
                                </div>

                                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                                    <p className="text-sm font-semibold text-amber-800">
                                        Lưu ý bảo mật
                                    </p>

                                    <p className="mt-1 text-xs leading-5 text-amber-700">
                                        API Key chỉ được hiển thị khi đăng ký
                                        camera. Hãy lưu lại và không chia sẻ
                                        khóa này cho người khác.
                                    </p>
                                </div>

                                <button
                                    onClick={() => {
                                        setShowAddModal(false);
                                        setCreatedCamera(null);
                                        setCopied(false);
                                        setError("");
                                    }}
                                    className="w-full rounded-xl bg-slate-900 py-3 text-sm font-medium text-white hover:bg-slate-800"
                                >
                                    Hoàn tất
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Edit Camera Modal */}
            {showEditModal && editingCamera && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
                    <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">

                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-bold text-slate-900">
                                Chỉnh sửa camera
                            </h2>

                            <button
                                onClick={() => {
                                    setShowEditModal(false);
                                    setEditingCamera(null);
                                    setError("");
                                }}
                                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        <form onSubmit={handleUpdateCamera} className="mt-6 space-y-5">
                            <div>
                                <label className="mb-2 block text-sm font-medium text-slate-700">
                                    Mã thiết bị
                                </label>

                                <input
                                    type="text"
                                    value={editDeviceId}
                                    onChange={(e) => setEditDeviceId(e.target.value)}
                                    minLength={1}
                                    maxLength={100}
                                    required
                                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500"
                                />
                            </div>

                            <div>
                                <label className="mb-2 block text-sm font-medium text-slate-700">
                                    Tên camera
                                </label>

                                <input
                                    type="text"
                                    value={editCameraName}
                                    onChange={(e) => setEditCameraName(e.target.value)}
                                    minLength={2}
                                    maxLength={150}
                                    required
                                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500"
                                />
                            </div>
                            <div>
                                <label className="mb-2 block text-sm font-medium text-slate-700">
                                    Địa chỉ luồng video (Stream URL)
                                </label>

                                <input
                                    type="url"
                                    value={editStreamUrl}
                                    onChange={(e) => setEditStreamUrl(e.target.value)}
                                    placeholder="http://192.168.1.106:81/stream"
                                    maxLength={500}
                                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                                />

                                <p className="mt-1 text-xs text-slate-400">
                                    Để trống nếu không muốn sử dụng luồng video.
                                </p>
                            </div>

                            {error && (
                                <p className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
                                    {error}
                                </p>
                            )}

                            <div className="flex justify-end gap-3 pt-2">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowEditModal(false);
                                        setEditingCamera(null);
                                        setError("");
                                    }}
                                    className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                                >
                                    Hủy
                                </button>

                                <button
                                    type="submit"
                                    disabled={updating}
                                    className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                                >
                                    {updating ? "Đang cập nhật..." : "Lưu thay đổi"}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

        </div>
    );
}

export default Cameras;
