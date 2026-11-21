"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "./api";
import type { MeResponse, Role } from "./types";

interface AuthContextValue {
  user: MeResponse | null;
  loading: boolean;
  signIn: (email: string) => Promise<MeResponse>;
  signOut: () => void;
  canAct: boolean;
  isAdmin: boolean;
  isViewer: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function roleAtLeast(role: Role, minimum: Role): boolean {
  const levels: Record<Role, number> = { viewer: 1, agent: 2, admin: 3 };
  return levels[role] >= levels[minimum];
}

export function AuthProvider({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const restoreSession = async () => {
      if (!api.getAccessToken()) {
        if (active) setLoading(false);
        if (pathname !== "/login") router.replace("/login");
        return;
      }

      try {
        const profile = await api.me();
        if (active) setUser(profile);
      } catch {
        api.setAccessToken(null);
        if (active) setUser(null);
        if (pathname !== "/login") router.replace("/login");
      } finally {
        if (active) setLoading(false);
      }
    };

    void restoreSession();
    return () => {
      active = false;
    };
  }, [pathname, router]);

  const signIn = useCallback(async (email: string) => {
    setLoading(true);
    try {
      await api.issueDemoToken({ email });
      const profile = await api.me();
      setUser(profile);
      return profile;
    } finally {
      setLoading(false);
    }
  }, []);

  const signOut = useCallback(() => {
    api.setAccessToken(null);
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo<AuthContextValue>(() => {
    const role = user?.role;
    return {
      user,
      loading,
      signIn,
      signOut,
      canAct: role ? roleAtLeast(role, "agent") : false,
      isAdmin: role === "admin",
      isViewer: role === "viewer",
    };
  }, [loading, signIn, signOut, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
