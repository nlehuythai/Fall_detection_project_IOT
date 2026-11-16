
import { useCallback, useEffect, useState } from "react";
import {
    Users,
    UserMinus,
    RefreshCw,
    ShieldCheck,
    Crown,
    User,
    MailPlus,
    Copy,
    Check,
    Bot,
    Send,
    Link,
    Clock
} from "lucide-react";

import { useHousehold } from "../../contexts/HouseholdContext";
import { useAuth } from "../../contexts/AuthContext";
import { householdService } from "../../services/householdService";


export default function Household() {
    const {
        household,
        householdId,
        loading: householdLoading,
    } = useHousehold();

    const { user } = useAuth();

    const [members, setMembers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [removingId, setRemovingId] = useState(null);

    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("member");
    const [inviteLoading, setInviteLoading] = useState(false);
    const [invitationToken, setInvitationToken] = useState("");

    const [acceptToken, setAcceptToken] = useState("");
    const [acceptLoading, setAcceptLoading] = useState(false);
    const [householdName, setHouseholdName] = useState("");
    const [createHouseholdLoading, setCreateHouseholdLoading] = useState(false);
    // Telegram
    const [telegramBot, setTelegramBot] = useState(null);
    const [telegramLinkData, setTelegramLinkData] = useState(null);
    const [telegramLoading, setTelegramLoading] = useState(false);
    const [telegramLinkLoading, setTelegramLinkLoading] = useState(false);
    const [telegramError, setTelegramError] = useState("");
    const [telegramSuccess, setTelegramSuccess] = useState("");
    const fetchMembers = useCallback(async () => {
        if (!householdId) return;

        try {
            setLoading(true);
            setError("");

            const data = await householdService.getMembers(householdId);
            setMembers(data);
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                "Không thể tải danh sách thành viên."
            );
        } finally {
            setLoading(false);
        }
    }, [householdId]);
    const fetchTelegramBot = useCallback(async () => {
        if (!householdId) return;

        try {
            setTelegramLoading(true);
            setTelegramError("");

            const data = await householdService.getTelegramBot(householdId);
            setTelegramBot(data);
        } catch (err) {
            setTelegramBot(null);
            setTelegramError(
                err.response?.data?.detail ||
                "Không thể tải thông tin Telegram Bot."
            );
        } finally {
            setTelegramLoading(false);
        }
    }, [householdId]);
    const handleCreateTelegramLink = async () => {
        try {
            setTelegramLinkLoading(true);
            setTelegramError("");
            setTelegramSuccess("");
            setTelegramLinkData(null);

            const data =
                await householdService.createTelegramLinkCode(householdId);

            setTelegramLinkData(data);
            setTelegramSuccess("Tạo mã liên kết Telegram thành công.");
        } catch (err) {
            setTelegramError(
                err.response?.data?.detail ||
                "Không thể tạo mã liên kết Telegram."
            );
        } finally {
            setTelegramLinkLoading(false);
        }
    };
    const handleOpenTelegram = () => {
        if (!telegramLinkData) return;

        const telegramUrl =
            `https://t.me/${telegramLinkData.bot_username}` +
            `?start=${encodeURIComponent(telegramLinkData.link_code)}`;

        window.open(telegramUrl, "_blank", "noopener,noreferrer");
    };
    const handleCreateInvite = async (e) => {
        e.preventDefault();

        try {
            setInviteLoading(true);
            setError("");
            setSuccess("");
            setInvitationToken("");

            const data = await householdService.createInvite(
                householdId,
                {
                    email: inviteEmail.trim(),
                    role: inviteRole,
                }
            );

            const token =
                data.invitation_token ||
                data.token;

            if (!token) {
                throw new Error("Backend không trả về invitation token.");
            }

            setInvitationToken(token);
            setSuccess("Tạo lời mời thành công.");
            setInviteEmail("");
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                err.message ||
                "Không thể tạo lời mời."
            );
        } finally {
            setInviteLoading(false);
        }
    };

    const handleAcceptInvite = async (e) => {
        e.preventDefault();

        try {
            setAcceptLoading(true);
            setError("");
            setSuccess("");

            await householdService.acceptInvite(acceptToken.trim());

            setSuccess("Tham gia hộ gia đình thành công.");
            setAcceptToken("");

            // Cập nhật danh sách hộ gia đình và thành viên
            window.location.reload();
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                "Không thể chấp nhận lời mời."
            );
        } finally {
            setAcceptLoading(false);
        }
    };
    const handleCreateHousehold = async (e) => {
        e.preventDefault();

        try {
            setCreateHouseholdLoading(true);
            setError("");
            setSuccess("");

            await householdService.create({
                household_name: householdName.trim(),
            });

            setSuccess("Tạo hộ gia đình thành công.");
            setHouseholdName("");

            window.location.reload();
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                "Không thể tạo hộ gia đình."
            );
        } finally {
            setCreateHouseholdLoading(false);
        }
    };
    useEffect(() => {
        fetchMembers();
    }, [fetchMembers]);
    useEffect(() => {
        fetchTelegramBot();
    }, [fetchTelegramBot]);
    const currentMember = members.find(
        (member) => Number(member.user_id) === Number(user?.id)
    );

    const canManageMembers = ["owner", "admin"].includes(
        currentMember?.role
    );

    const handleRemoveMember = async (member) => {
        const confirmed = window.confirm(
            `Bạn có chắc chắn muốn xóa ${member.full_name} khỏi hộ gia đình?`
        );

        if (!confirmed) return;

        try {
            setRemovingId(member.user_id);
            setError("");
            setSuccess("");

            await householdService.removeMember(
                householdId,
                member.user_id
            );

            setSuccess(
                `Đã xóa ${member.full_name} khỏi hộ gia đình.`
            );

            await fetchMembers();
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                "Không thể xóa thành viên."
            );
        } finally {
            setRemovingId(null);
        }
    };

    if (householdLoading) {
        return (
            <div className="p-6 text-gray-500">
                Đang tải dữ liệu hộ gia đình...
            </div>
        );
    }

    {
        householdId ? (
            <>
                {/* Household information */}

                {/* Invite member */}

                {/* Members list */}
            </>
        ) : (
            <div className="rounded-xl border border-gray-200 bg-white p-5">
                <div className="flex items-center gap-3">
                    <Users className="text-blue-600" size={24} />

                    <div>
                        <h2 className="font-semibold text-gray-900">
                            Bạn chưa tham gia hộ gia đình
                        </h2>

                        <p className="text-sm text-gray-500">
                            Nhập mã lời mời bên dưới để tham gia hộ gia đình.
                        </p>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">
                        Quản lý hộ gia đình
                    </h1>

                    <p className="mt-1 text-sm text-gray-500">
                        Quản lý thành viên và quyền truy cập trong hộ gia đình.
                    </p>
                </div>

                <button
                    onClick={fetchMembers}
                    disabled={loading}
                    className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                    <RefreshCw
                        size={16}
                        className={loading ? "animate-spin" : ""}
                    />
                    Làm mới
                </button>
            </div>

            {/* Household information */}
            {/* Create household - only when user has no household */}
            {!householdId && (
                <div className="rounded-xl border border-gray-200 bg-white p-5">
                    <div className="mb-4 flex items-center gap-3">
                        <div className="rounded-lg bg-blue-50 p-2 text-blue-600">
                            <Users size={21} />
                        </div>

                        <div>
                            <h2 className="font-semibold text-gray-900">
                                Tạo hộ gia đình mới
                            </h2>
                            <p className="text-sm text-gray-500">
                                Tạo hộ gia đình để quản lý camera và sự kiện té ngã.
                            </p>
                        </div>
                    </div>

                    <form onSubmit={handleCreateHousehold} className="space-y-3">
                        <input
                            type="text"
                            required
                            minLength={1}
                            maxLength={150}
                            value={householdName}
                            onChange={(e) => setHouseholdName(e.target.value)}
                            placeholder="Ví dụ: Gia đình kiểm thử B"
                            className="w-full rounded-lg border border-gray-300 px-3 py-2 outline-none focus:border-blue-500"
                        />

                        <button
                            type="submit"
                            disabled={createHouseholdLoading || !householdName.trim()}
                            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                        >
                            {createHouseholdLoading ? "Đang tạo..." : "Tạo hộ gia đình"}
                        </button>
                    </form>
                </div>
            )}

            {/* Telegram Integration */}
            {householdId && (
                <div className="rounded-xl border border-gray-200 bg-white p-5">
                    <div className="mb-4 flex items-center gap-3">
                        <div className="rounded-lg bg-sky-50 p-2 text-sky-600">
                            <Bot size={22} />
                        </div>

                        <div>
                            <h2 className="font-semibold text-gray-900">
                                Liên kết Telegram
                            </h2>
                            <p className="text-sm text-gray-500">
                                Kết nối tài khoản Telegram để nhận cảnh báo té ngã.
                            </p>
                        </div>
                    </div>

                    {telegramLoading ? (
                        <p className="text-sm text-gray-500">
                            Đang tải thông tin Telegram...
                        </p>
                    ) : telegramBot?.bot_username ? (
                        <>
                            <div className="mb-4 rounded-lg bg-gray-50 p-3">
                                <p className="text-xs text-gray-500">
                                    Telegram Bot của hộ gia đình
                                </p>
                                <p className="mt-1 font-medium text-gray-900">
                                    @{telegramBot.bot_username.replace(/^@/, "")}
                                </p>
                                <p className="mt-1 text-xs text-gray-500">
                                    Trạng thái: {telegramBot.is_active ? "Đang hoạt động" : "Đã tắt"}
                                </p>
                            </div>

                            {telegramBot.is_active ? (
                                <>
                                    <button
                                        type="button"
                                        onClick={handleCreateTelegramLink}
                                        disabled={telegramLinkLoading}
                                        className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                                    >
                                        <Link size={16} />
                                        {telegramLinkLoading
                                            ? "Đang tạo mã..."
                                            : "Tạo mã liên kết"}
                                    </button>

                                    {telegramLinkData && (
                                        <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4">
                                            <p className="font-medium text-blue-900">
                                                Mã liên kết đã được tạo
                                            </p>

                                            <p className="mt-2 break-all text-sm text-blue-800">
                                                {telegramLinkData.link_code}
                                            </p>

                                            <div className="mt-2 flex items-center gap-2 text-xs text-blue-700">
                                                <Clock size={14} />
                                                Hết hạn:{" "}
                                                {new Date(
                                                    telegramLinkData.expires_at
                                                ).toLocaleString("vi-VN")}
                                            </div>

                                            <button
                                                type="button"
                                                onClick={handleOpenTelegram}
                                                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700"
                                            >
                                                <Send size={16} />
                                                Mở Telegram
                                            </button>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <p className="text-sm text-amber-600">
                                    Bot Telegram hiện đã bị vô hiệu hóa.
                                </p>
                            )}
                        </>
                    ) : (
                        <p className="text-sm text-gray-500">
                            Hộ gia đình chưa cấu hình Telegram Bot.
                            Vui lòng liên hệ chủ hộ để thiết lập Bot.
                        </p>
                    )}

                    {telegramError && (
                        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
                            {telegramError}
                        </div>
                    )}

                    {telegramSuccess && (
                        <div className="mt-3 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
                            {telegramSuccess}
                        </div>
                    )}
                </div>
            )}

            <div className="rounded-xl border border-gray-200 bg-white p-5">
                <div className="flex items-center gap-3">
                    <div className="rounded-xl bg-blue-50 p-3 text-blue-600">
                        <Users size={24} />
                    </div>

                    <div>
                        <h2 className="font-semibold text-gray-900">
                            {household?.household_name}
                        </h2>

                        <p className="text-sm text-gray-500">
                            Mã hộ gia đình: #{householdId}
                        </p>
                    </div>
                </div>
            </div>

            {/* Messages */}
            {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
                    {error}
                </div>
            )}

            {success && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
                    {success}
                </div>
            )}

            {/* Invite member */}
            {canManageMembers && (
                <div className="rounded-xl border border-gray-200 bg-white p-5">
                    <div className="mb-4 flex items-center gap-3">
                        <div className="rounded-lg bg-blue-50 p-2 text-blue-600">
                            <MailPlus size={21} />
                        </div>

                        <div>
                            <h2 className="font-semibold text-gray-900">
                                Mời thành viên
                            </h2>
                            <p className="text-sm text-gray-500">
                                Tạo lời mời tham gia hộ gia đình.
                            </p>
                        </div>
                    </div>

                    <form onSubmit={handleCreateInvite} className="space-y-4">
                        <div>
                            <label className="mb-1 block text-sm font-medium text-gray-700">
                                Email thành viên
                            </label>

                            <input
                                type="email"
                                required
                                value={inviteEmail}
                                onChange={(e) => setInviteEmail(e.target.value)}
                                placeholder="example@gmail.com"
                                className="w-full rounded-lg border border-gray-300 px-3 py-2 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                            />
                        </div>

                        <div>
                            <label className="mb-1 block text-sm font-medium text-gray-700">
                                Vai trò
                            </label>

                            <select
                                value={inviteRole}
                                onChange={(e) => setInviteRole(e.target.value)}
                                className="w-full rounded-lg border border-gray-300 px-3 py-2 outline-none focus:border-blue-500"
                            >
                                <option value="member">Thành viên</option>
                                <option value="admin">Quản trị viên</option>
                            </select>
                        </div>

                        <button
                            type="submit"
                            disabled={inviteLoading || !canManageMembers}
                            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                        >
                            <MailPlus size={16} />
                            {inviteLoading ? "Đang tạo..." : "Tạo lời mời"}
                        </button>
                    </form>

                    {invitationToken && (
                        <div className="mt-4 rounded-lg border border-green-200 bg-green-50 p-4">
                            <p className="mb-2 text-sm font-medium text-green-800">
                                Mã lời mời đã được tạo
                            </p>

                            <div className="flex flex-col gap-2 sm:flex-row">
                                <input
                                    readOnly
                                    value={invitationToken}
                                    className="min-w-0 flex-1 rounded-lg border border-green-200 bg-white px-3 py-2 text-sm"
                                />

                                <button
                                    type="button"
                                    onClick={() => {
                                        navigator.clipboard.writeText(invitationToken);
                                        setSuccess("Đã sao chép mã lời mời.");
                                    }}
                                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-green-600 px-3 py-2 text-sm text-white hover:bg-green-700"
                                >
                                    <Copy size={15} />
                                    Sao chép
                                </button>
                            </div>

                            <p className="mt-2 text-xs text-green-700">
                                Chia sẻ mã này với người được mời. Mã có thời hạn 7 ngày.
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Accept invitation */}
            {!householdId && (
                <div className="rounded-xl border border-gray-200 bg-white p-5">
                    <div className="mb-4 flex items-center gap-3">
                        <div className="rounded-lg bg-purple-50 p-2 text-purple-600">
                            <Users size={21} />
                        </div>

                        <div>
                            <h2 className="font-semibold text-gray-900">
                                Tham gia hộ gia đình
                            </h2>
                            <p className="text-sm text-gray-500">
                                Nhập mã lời mời để tham gia một hộ gia đình khác.
                            </p>
                        </div>
                    </div>

                    <form onSubmit={handleAcceptInvite} className="space-y-3">
                        <input
                            type="text"
                            required
                            value={acceptToken}
                            onChange={(e) => setAcceptToken(e.target.value)}
                            placeholder="Nhập invitation token"
                            className="w-full rounded-lg border border-gray-300 px-3 py-2 outline-none focus:border-purple-500"
                        />

                        <button
                            type="submit"
                            disabled={acceptLoading}
                            className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
                        >
                            {acceptLoading ? "Đang xử lý..." : "Chấp nhận lời mời"}
                        </button>
                    </form>
                </div>
            )}
            {/* Members */}
            <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
                <div className="flex items-center justify-between border-b border-gray-100 p-5">
                    <div>
                        <h2 className="font-semibold text-gray-900">
                            Thành viên hộ gia đình
                        </h2>

                        <p className="mt-1 text-sm text-gray-500">
                            {members.length} thành viên
                        </p>
                    </div>

                    <Users size={22} className="text-gray-400" />
                </div>

                {loading ? (
                    <div className="p-8 text-center text-gray-500">
                        Đang tải danh sách thành viên...
                    </div>
                ) : members.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">
                        Chưa có thành viên nào.
                    </div>
                ) : (
                    <div className="divide-y divide-gray-100">
                        {members.map((member) => {
                            const isOwner = member.role === "owner";
                            const isCurrentUser =
                                Number(member.user_id) === Number(user?.id);

                            return (
                                <div
                                    key={member.user_id}
                                    className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between"
                                >
                                    <div className="flex min-w-0 items-center gap-3">
                                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                                            <User size={21} />
                                        </div>

                                        <div className="min-w-0">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <p className="font-medium text-gray-900">
                                                    {member.full_name}
                                                </p>

                                                {isCurrentUser && (
                                                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
                                                        Bạn
                                                    </span>
                                                )}
                                            </div>

                                            <p className="truncate text-sm text-gray-500">
                                                {member.email}
                                            </p>

                                            <p className="mt-1 text-xs text-gray-400">
                                                Tham gia:{" "}
                                                {member.joined_at
                                                    ? new Date(
                                                        member.joined_at
                                                    ).toLocaleDateString("vi-VN")
                                                    : "Không rõ"}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3">
                                        <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                                            {isOwner ? (
                                                <Crown size={13} />
                                            ) : (
                                                <ShieldCheck size={13} />
                                            )}

                                            {isOwner
                                                ? "Chủ hộ"
                                                : member.role === "admin"
                                                    ? "Quản trị viên"
                                                    : "Thành viên"}
                                        </span>

                                        {canManageMembers &&
                                            !isOwner &&
                                            !isCurrentUser && (
                                                <button
                                                    onClick={() =>
                                                        handleRemoveMember(member)
                                                    }
                                                    disabled={
                                                        removingId === member.user_id
                                                    }
                                                    title="Xóa thành viên"
                                                    className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                                                >
                                                    <UserMinus size={16} />

                                                    {removingId === member.user_id
                                                        ? "Đang xóa..."
                                                        : "Xóa"}
                                                </button>
                                            )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {!canManageMembers && members.length > 0 && (
                <p className="text-sm text-gray-500">
                    Bạn không có quyền quản lý thành viên trong hộ gia đình này.
                </p>
            )}
        </div>
    );
}
