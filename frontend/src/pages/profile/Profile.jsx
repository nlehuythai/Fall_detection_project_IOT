
import { useEffect, useState } from "react";
import {
    UserCircle,
    Mail,
    Calendar,
    ShieldCheck,
    Pencil,
    Lock,
    Save,
    X,
    Loader2,
} from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { authService } from "../../services/authService";
function Profile() {
    const { user, updateUser } = useAuth();
    const [isEditing, setIsEditing] = useState(false);
    const [fullName, setFullName] = useState(user?.full_name || "");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    const [changingPassword, setChangingPassword] = useState(false);
    const [passwordError, setPasswordError] = useState("");
    const [passwordSuccess, setPasswordSuccess] = useState("");
    const handleSaveProfile = async () => {
        const trimmedName = fullName.trim();

        if (trimmedName.length < 2 || trimmedName.length > 150) {
            setError("Họ tên phải có từ 2 đến 150 ký tự.");
            return;
        }

        try {
            setSaving(true);
            setError("");
            setSuccess("");

            const updatedUser = await authService.updateProfile({
                full_name: trimmedName,
            });

            updateUser(updatedUser);
            setFullName(updatedUser.full_name);
            setIsEditing(false);
            setSuccess("Cập nhật thông tin thành công!");
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                "Không thể cập nhật thông tin. Vui lòng thử lại."
            );
        } finally {
            setSaving(false);
        }
    };
    const handleChangePassword = async () => {
        setPasswordError("");
        setPasswordSuccess("");

        if (!currentPassword || !newPassword || !confirmPassword) {
            setPasswordError("Vui lòng nhập đầy đủ thông tin.");
            return;
        }

        if (newPassword.length < 8 || newPassword.length > 128) {
            setPasswordError("Mật khẩu mới phải có từ 8 đến 128 ký tự.");
            return;
        }

        if (newPassword !== confirmPassword) {
            setPasswordError("Mật khẩu xác nhận không khớp.");
            return;
        }

        if (currentPassword === newPassword) {
            setPasswordError("Mật khẩu mới phải khác mật khẩu hiện tại.");
            return;
        }

        try {
            setChangingPassword(true);

            await authService.changePassword({
                current_password: currentPassword,
                new_password: newPassword,
            });

            setCurrentPassword("");
            setNewPassword("");
            setConfirmPassword("");

            setPasswordSuccess("Đổi mật khẩu thành công!");
        } catch (err) {
            setPasswordError(
                err.response?.data?.detail ||
                "Không thể đổi mật khẩu. Vui lòng thử lại."
            );
        } finally {
            setChangingPassword(false);
        }
    };
    useEffect(() => {
        setFullName(user?.full_name || "");
    }, [user]);

    const getInitials = (name) => {
        return name
            ?.trim()
            .split(/\s+/)
            .map((word) => word[0])
            .join("")
            .slice(-2)
            .toUpperCase() || "U";
    };

    const formatDate = (date) => {
        if (!date) return "Không có dữ liệu";

        return new Date(date).toLocaleDateString("vi-VN", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        });
    };

    return (
        <div className="mx-auto max-w-5xl space-y-6">

            {/* Page Header */}
            <div>
                <h1 className="text-2xl font-bold text-slate-900">
                    My Profile
                </h1>
                <p className="mt-1 text-sm text-slate-500">
                    Manage your personal information and account security.
                </p>
            </div>


            {/* Profile Overview */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">

                    {/* Avatar and User Information */}
                    <div className="flex min-w-0 items-center gap-5">
                        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-2xl font-bold text-white shadow-md ring-4 ring-blue-50">
                            {getInitials(user?.full_name)}
                        </div>

                        <div className="min-w-0">
                            <h2 className="truncate text-xl font-bold text-slate-900">
                                {user?.full_name || "FallGuard User"}
                            </h2>

                            <p className="mt-1 flex items-center gap-2 truncate text-sm text-slate-500">
                                <Mail size={15} className="shrink-0" />
                                {user?.email}
                            </p>

                            <p className="mt-2 text-xs font-medium text-slate-400">
                                Account ID: #{user?.id}
                            </p>
                        </div>
                    </div>

                    {/* Account Status */}
                    <div className="flex shrink-0 items-center">
                        <span className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold ${user?.is_active
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-red-50 text-red-700"
                            }`}>
                            <span className={`h-2 w-2 rounded-full ${user?.is_active ? "bg-emerald-500" : "bg-red-500"
                                }`} />

                            {user?.is_active ? "Active Account" : "Inactive Account"}
                        </span>
                    </div>

                </div>
            </div>



            {/* Personal Information */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

                <div className="mb-6 flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">
                            Personal Information
                        </h3>
                        <p className="mt-1 text-sm text-slate-500">
                            Your account information.
                        </p>
                    </div>

                    {!isEditing && (
                        <button
                            onClick={() => setIsEditing(true)}
                            className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                        >
                            <Pencil size={16} />
                            Edit Profile
                        </button>
                    )}
                </div>

                <div className="grid gap-6 md:grid-cols-2">

                    {/* Full Name */}
                    <div>
                        <label className="mb-2 block text-sm font-medium text-slate-600">
                            Full Name
                        </label>

                        {isEditing ? (
                            <input
                                type="text"
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                                className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                                minLength={2}
                                maxLength={150}
                            />
                        ) : (
                            <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3">
                                <UserCircle size={19} className="text-slate-400" />
                                <span className="text-sm font-medium text-slate-800">
                                    {user?.full_name || "N/A"}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Email */}
                    <div>
                        <label className="mb-2 block text-sm font-medium text-slate-600">
                            Email Address
                        </label>

                        <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3">
                            <Mail size={19} className="text-slate-400" />
                            <span className="text-sm font-medium text-slate-800">
                                {user?.email || "N/A"}
                            </span>
                        </div>
                    </div>

                    {/* Account ID */}
                    <div>
                        <label className="mb-2 block text-sm font-medium text-slate-600">
                            Account ID
                        </label>

                        <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3">
                            <ShieldCheck size={19} className="text-slate-400" />
                            <span className="text-sm font-medium text-slate-800">
                                #{user?.id || "N/A"}
                            </span>
                        </div>
                    </div>

                    {/* Created Date */}
                    <div>
                        <label className="mb-2 block text-sm font-medium text-slate-600">
                            Joined Date
                        </label>

                        <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3">
                            <Calendar size={19} className="text-slate-400" />
                            <span className="text-sm font-medium text-slate-800">
                                {formatDate(user?.created_at)}
                            </span>
                        </div>
                    </div>
                </div>
                {error && (
                    <p className="mt-4 text-sm text-red-600">{error}</p>
                )}

                {success && (
                    <p className="mt-4 text-sm text-green-600">{success}</p>
                )}
                {isEditing && (
                    <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-5">
                        <button
                            onClick={() => {
                                setFullName(user?.full_name || "");
                                setIsEditing(false);
                            }}
                            className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                        >
                            <X size={16} />
                            Cancel
                        </button>

                        <button
                            onClick={handleSaveProfile}
                            disabled={saving}
                            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {saving ? (
                                <Loader2 size={16} className="animate-spin" />
                            ) : (
                                <Save size={16} />
                            )}
                            {saving ? "Saving..." : "Save Changes"}
                        </button>
                    </div>
                )}
            </div>


            {/* Account Security */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                        <Lock size={21} />
                    </div>

                    <div>
                        <h3 className="font-bold text-slate-900">
                            Account Security
                        </h3>
                        <p className="text-sm text-slate-500">
                            Change your password to keep your account secure.
                        </p>
                    </div>
                </div>

                <div className="mt-6 space-y-4">
                    <div>
                        <label className="mb-2 block text-sm font-medium text-slate-600">
                            Current Password
                        </label>
                        <input
                            type="password"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            placeholder="Enter current password"
                            autoComplete="current-password"
                            className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                        />
                    </div>

                    <div>
                        <label className="mb-2 block text-sm font-medium text-slate-600">
                            New Password
                        </label>
                        <input
                            type="password"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            placeholder="Enter new password"
                            autoComplete="new-password"
                            className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                        />
                    </div>

                    <div>
                        <label className="mb-2 block text-sm font-medium text-slate-600">
                            Confirm New Password
                        </label>
                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            placeholder="Confirm new password"
                            autoComplete="new-password"
                            className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                        />
                    </div>

                    {passwordError && (
                        <p className="text-sm text-red-600">
                            {passwordError}
                        </p>
                    )}

                    {passwordSuccess && (
                        <p className="text-sm text-green-600">
                            {passwordSuccess}
                        </p>
                    )}

                    <div className="flex justify-end border-t border-slate-100 pt-5">
                        <button
                            onClick={handleChangePassword}
                            disabled={changingPassword}
                            className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {changingPassword ? (
                                <Loader2 size={16} className="animate-spin" />
                            ) : (
                                <Lock size={16} />
                            )}

                            {changingPassword ? "Updating..." : "Change Password"}
                        </button>
                    </div>
                </div>
            </div>


        </div>
    );
}

export default Profile;
