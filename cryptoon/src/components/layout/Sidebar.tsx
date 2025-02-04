// Sidebar Component
const Sidebar = ({ isOpen }: { isOpen: boolean }) => {
  const menuItems = [
    { label: 'Dashboard', href: '/dashboard' },
    { label: 'Contratos', href: '/dashboard/contract' },
    { label: 'Chaves', href: '/dashboard/keys' },
    { label: 'Logs', href: '/dashboard/logs' },
    { label: 'Crypto', href: '/dashboard/crypto' },
    { label: 'Histórico', href: '/dashboard/history' },
  ];

  return (
    <aside 
      className={`fixed left-0 top-16 h-[calc(100vh-4rem)] bg-white border-r border-gray-200 transition-all duration-300 ${
        isOpen ? 'w-64' : 'w-20'
      }`}
    >
      <nav className="p-4">
        <ul className="space-y-2">
          {menuItems.map((item) => (
            <li key={item.href}>
              <a
                href={item.href}
                className="flex items-center p-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                {/* Você pode adicionar ícones aqui */}
                <span className={`${!isOpen && 'hidden'} ml-3`}>{item.label}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
};