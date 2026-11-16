import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
    LayoutDashboard,
    Camera,
    AlertTriangle,
    Users,
    UserCircle,
    LogOut,
    ShieldCheck,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const menuItems = [
    {
        label: "Dashboard",
        path: "/dashboard",
        icon: LayoutDashboard,
    },
    {
        label: "Cameras",
        path: "/cameras",
        icon: Camera,
    },
    {
        label: "Fall Events",
        path: "/events",
        icon: AlertTriangle,
    },
    {
        label: "Household",
        path: "/household",
        icon: Users,
    },
    {
        label: "Profile",
        path: "/profile",
        icon: UserCircle,
    },
];

function MainLayout() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate("/login");
    };

    return (
        <div className="flex min-h-screen bg-slate-50">
            {/* Sidebar */}
            <aside className="fixed inset-y-0 left-0 z-20 flex w-64 flex-col border-r border-slate-200 bg-white">
                <div className="flex h-20 items-center gap-3 border-b border-slate-200 px-6">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white">
                        <ShieldCheck size={24} />
                    </div>

                    <div>
                        <h1 className="text-lg font-bold text-slate-900">
                            FallGuard
                        </h1>
                        <p className="text-xs text-slate-500">
                            IoT Monitoring
                        </p>
                    </div>
                </div>

                <nav className="flex-1 space-y-2 px-4 py-6">
                    <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Main Menu
                    </p>

                    {menuItems.map((item) => {
                        const Icon = item.icon;

                        return (
                            <NavLink
                                key={item.path}
                                to={item.path}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition ${isActive
                                        ? "bg-blue-50 text-blue-700"
                                        : "text-slate-600 hover:bg-slate-100"
                                    }`
                                }
                            >
                                <Icon size={20} />
                                {item.label}
                            </NavLink>
                        );
                    })}
                </nav>

                <div className="border-t border-slate-200 p-4">
                    <div className="mb-4 px-2">
                        <p className="truncate text-sm font-semibold text-slate-800">
                            {user?.full_name || "FallGuard User"}
                        </p>
                        <p className="truncate text-xs text-slate-500">
                            {user?.email || ""}
                        </p>
                    </div>

                    <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-red-600 transition hover:bg-red-50"
                    >
                        <LogOut size={20} />
                        Sign Out
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <div className="ml-64 flex min-h-screen flex-1 flex-col">
                <header className="flex h-20 items-center justify-between border-b border-slate-200 bg-white px-8">
                    <h2 className="text-sm font-medium text-slate-500">
                        Fall Detection Management System
                    </h2>

                    <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700">
                            {user?.full_name?.charAt(0)?.toUpperCase() || "U"}
                        </div>
                    </div>
                </header>

                <main className="flex-1 p-8">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}

export default MainLayout;