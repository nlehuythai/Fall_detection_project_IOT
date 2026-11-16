import { UserCircle } from "lucide-react";

function Profile() {
    return (
        <div>
            <div className="flex items-center gap-3">
                <UserCircle className="text-blue-600" size={28} />
                <h1 className="text-2xl font-bold text-slate-900">
                    Profile
                </h1>
            </div>
            <p className="mt-2 text-slate-500">
                View and manage your account information.
            </p>
        </div>
    );
}

export default Profile;