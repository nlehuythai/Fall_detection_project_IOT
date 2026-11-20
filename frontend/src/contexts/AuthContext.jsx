
import {
    createContext,
    useContext,
    useEffect,
    useState,
} from "react";

import { authService } from "../services/authService";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);

    const [token, setToken] = useState(
        () => localStorage.getItem("access_token")
    );

    const [loading, setLoading] = useState(true);

    // Khôi phục thông tin người dùng khi tải lại trang
    useEffect(() => {
        const restoreUser = async () => {
            const savedToken = localStorage.getItem("access_token");

            if (!savedToken) {
                setUser(null);
                setToken(null);
                setLoading(false);
                return;
            }

            try {
                const userData = await authService.getMe();

                setToken(savedToken);
                setUser(userData);
            } catch (error) {
                localStorage.removeItem("access_token");
                setToken(null);
                setUser(null);
            } finally {
                setLoading(false);
            }
        };

        restoreUser();
    }, []);

    // Xử lý khi token hết hạn
    useEffect(() => {
        const handleSessionExpired = () => {
            localStorage.removeItem("access_token");

            setToken(null);
            setUser(null);

            window.location.href = "/login";
        };

        window.addEventListener(
            "auth:session-expired",
            handleSessionExpired
        );

        return () => {
            window.removeEventListener(
                "auth:session-expired",
                handleSessionExpired
            );
        };
    }, []);

    // Đăng nhập
    const login = (accessToken, userData) => {
        localStorage.setItem("access_token", accessToken);

        setToken(accessToken);
        setUser(userData);
    };

    // Đăng xuất
    const logout = () => {
        localStorage.removeItem("access_token");

        setToken(null);
        setUser(null);
    };
    const updateUser = (userData) => {
        setUser(userData);
    };
    return (
        <AuthContext.Provider
            value={{
                user,
                token,
                loading,
                login,
                logout,
                updateUser,
                isAuthenticated: !!token,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}
export function useAuth() {
    return useContext(AuthContext);
}
