import ChatPage from '@/pages/ChatPage';
import Sidebar from '@/components/sidebar/Sidebar';
import SettingsDrawer from '@/components/settings/SettingsDrawer';

export default function App() {
  return (
    <div className="h-full bg-neutral-900 text-neutral-100">
      <ChatPage />
      <Sidebar />
      <SettingsDrawer />
    </div>
  );
}
