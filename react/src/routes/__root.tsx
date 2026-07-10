import ErrorBoundary from '@/components/common/ErrorBoundary'
import SettingsDialog from '@/components/settings/dialog'
import { createRootRoute, Outlet } from '@tanstack/react-router'

export const Route = createRootRoute({
  component: () => (
    <>
      <Outlet />
      <SettingsDialog />
    </>
  ),
  errorComponent: ErrorBoundary,
})
