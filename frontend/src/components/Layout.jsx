import React, { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
    LayoutDashboard,
    FolderKanban,
    Settings,
    Plus,
    ChevronLeft,
    ChevronRight,
    Sparkles,
    Menu,
    X,
    Sun,
    Moon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from '@/components/ui/tooltip'
import { useTheme } from '@/components/ThemeProvider'

const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/projects', icon: FolderKanban, label: 'Projects' },
    { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
    const [collapsed, setCollapsed] = useState(false)
    const [mobileOpen, setMobileOpen] = useState(false)
    const location = useLocation()
    const { theme, toggleTheme } = useTheme()

    return (
        <div className="flex h-screen overflow-hidden bg-background">
            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside
                className={`
                    fixed md:relative z-50 h-full flex flex-col
                    border-r border-sidebar-border bg-sidebar
                    transition-all duration-300 ease-in-out
                    ${collapsed ? 'w-[68px]' : 'w-64'}
                    ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
                `}
            >
                {/* Logo */}
                <div className="flex items-center gap-3 px-4 h-16 shrink-0">
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/15 shrink-0">
                        <Sparkles className="w-5 h-5 text-primary" />
                    </div>
                    {!collapsed && (
                        <span className="text-lg font-bold tracking-tight gradient-text">
                            Modifai
                        </span>
                    )}
                    {/* Mobile close */}
                    <Button
                        variant="ghost"
                        size="icon"
                        className="ml-auto md:hidden h-8 w-8"
                        onClick={() => setMobileOpen(false)}
                    >
                        <X className="w-4 h-4" />
                    </Button>
                </div>

                <Separator className="opacity-50" />

                {/* New Project CTA */}
                <div className="px-3 py-4">
                    <NavLink to="/projects/new" onClick={() => setMobileOpen(false)}>
                        <Button
                            className={`w-full gap-2 bg-primary hover:bg-primary/90 text-primary-foreground glow transition-all duration-200 ${collapsed ? 'px-0 justify-center' : ''
                                }`}
                            size={collapsed ? 'icon' : 'default'}
                        >
                            <Plus className="w-4 h-4 shrink-0" />
                            {!collapsed && <span>New Project</span>}
                        </Button>
                    </NavLink>
                </div>

                {/* Navigation */}
                <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
                    {navItems.map(({ to, icon: Icon, label }) => {
                        const isActive =
                            to === '/'
                                ? location.pathname === '/'
                                : location.pathname.startsWith(to)

                        const link = (
                            <NavLink
                                key={to}
                                to={to}
                                onClick={() => setMobileOpen(false)}
                                className={`
                                    flex items-center gap-3 rounded-lg px-3 py-2.5
                                    text-sm font-medium transition-all duration-200
                                    ${collapsed ? 'justify-center px-0' : ''}
                                    ${isActive
                                        ? 'bg-sidebar-accent text-sidebar-primary'
                                        : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
                                    }
                                `}
                            >
                                <Icon className={`w-5 h-5 shrink-0 ${isActive ? 'text-primary' : ''}`} />
                                {!collapsed && label}
                            </NavLink>
                        )

                        if (collapsed) {
                            return (
                                <Tooltip key={to} delayDuration={0}>
                                    <TooltipTrigger asChild>{link}</TooltipTrigger>
                                    <TooltipContent side="right" className="font-medium">
                                        {label}
                                    </TooltipContent>
                                </Tooltip>
                            )
                        }
                        return link
                    })}
                </nav>

                {/* Bottom controls */}
                <div className="hidden md:flex items-center gap-1 px-3 py-3 border-t border-sidebar-border">
                    <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                            <Button
                                variant="ghost"
                                size="icon"
                                className={`h-8 w-8 text-muted-foreground hover:text-foreground transition-colors ${collapsed ? 'hidden' : ''}`}
                                onClick={toggleTheme}
                            >
                                {theme === 'dark' ? (
                                    <Sun className="w-4 h-4" />
                                ) : (
                                    <Moon className="w-4 h-4" />
                                )}
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="font-medium">
                            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
                        </TooltipContent>
                    </Tooltip>
                    <Button
                        variant="ghost"
                        size="icon"
                        className={`h-8 w-8 text-muted-foreground hover:text-foreground ${collapsed ? 'mx-auto' : 'ml-auto'
                            }`}
                        onClick={() => setCollapsed(!collapsed)}
                    >
                        {collapsed ? (
                            <ChevronRight className="w-4 h-4" />
                        ) : (
                            <ChevronLeft className="w-4 h-4" />
                        )}
                    </Button>
                </div>
            </aside>

            {/* Main content */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Top bar (mobile) */}
                <header className="flex md:hidden items-center h-14 px-4 border-b border-border bg-background/80 backdrop-blur-md shrink-0">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9"
                        onClick={() => setMobileOpen(true)}
                    >
                        <Menu className="w-5 h-5" />
                    </Button>
                    <div className="flex items-center gap-2 ml-3">
                        <Sparkles className="w-4 h-4 text-primary" />
                        <span className="text-sm font-semibold gradient-text">Modifai</span>
                    </div>
                </header>

                {/* Page content */}
                <main className="flex-1 overflow-y-auto">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}
