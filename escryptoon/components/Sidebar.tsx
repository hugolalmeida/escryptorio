'use client'
import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Home, 
  FileText, 
  Menu, 
  X,
  Building2
} from 'lucide-react';
import styles from '../styles/Sidebar.module.css';

const Sidebar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  const menuItems = [
    {
      path: '/',
      name: 'Início',
      icon: Home
    },
    {
      path: '/formulario',
      name: 'Formulário',
      icon: FileText
    },
    {
      path: '/sobre',
      name: 'Sobre',
      icon: Building2
    },
  ];

  return (
    <>
      <button 
        className={styles.mobileButton}
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {isOpen && (
        <div 
          className={styles.overlay}
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside className={`${styles.sidebar} ${isOpen ? styles.active : ''}`}>
        <div className={styles.sidebarContent}>
          <div className={styles.logo}>
            <h1>Escritorio Crypto</h1>
          </div>

          <nav className={styles.navigation}>
            <ul>
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.path;

                return (
                  <li key={item.path}>
                    <Link
                      href={item.path}
                      className={`${styles.navLink} ${isActive ? styles.active : ''}`}
                      onClick={() => setIsOpen(false)}
                    >
                      <Icon size={20} />
                      <span>{item.name}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className={styles.footer}>
            <p>© 2025 Escritorio Crypto</p>
          </div>
        </div>
      </aside>

      <div className={styles.content} />
    </>
  );
};

export default Sidebar;