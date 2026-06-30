import { forwardRef, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { authApi } from '../api/client';
import { toast } from './Toast';
import { X } from 'lucide-react';

interface Props {
  bound: boolean;
  accountName?: string;
  userUid?: string;
  onBind: () => void;
  onChanged: () => void;
  popoverPlacement?: 'top' | 'bottom';
  anchorWrapperRef?: React.RefObject<HTMLElement | null>;
}

export const AccountButton = forwardRef<HTMLButtonElement, Props>(
  function AccountButton(
    { bound, accountName, userUid, onBind, onChanged, popoverPlacement = 'bottom', anchorWrapperRef },
    forwardedBtnRef,
  ) {
    const { t } = useTranslation('app');
    const [menuOpen, setMenuOpen] = useState(false);
    const [confirmUnbind, setConfirmUnbind] = useState(false);
    const wrapRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      if (!menuOpen) return;
      const onDoc = (e: MouseEvent) => {
        const target = e.target as Node;
        if (wrapRef.current?.contains(target)) return;
        if (anchorWrapperRef?.current?.contains(target)) return;
        setMenuOpen(false);
      };
      document.addEventListener('mousedown', onDoc);
      return () => document.removeEventListener('mousedown', onDoc);
    }, [menuOpen, anchorWrapperRef]);

    useEffect(() => {
      const handleEsc = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          setMenuOpen(false);
        }
      };
      document.addEventListener('keydown', handleEsc);
      return () => document.removeEventListener('keydown', handleEsc);
    }, []);

    const handleClick = (e: React.MouseEvent) => {
      e.stopPropagation();
      if (bound) setMenuOpen((v) => !v);
      else onBind();
    };

    return (
      <div ref={wrapRef} className="relative shrink-0">
        <button
          ref={forwardedBtnRef}
          type="button"
          onClick={handleClick}
          aria-haspopup={bound ? 'menu' : 'dialog'}
          aria-expanded={bound ? menuOpen : undefined}
          className="relative inline-flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-colors focus-visible:ring-2 focus-visible:ring-[#00d4ff] focus-visible:outline-none overflow-hidden"
          style={{ width: 32, height: 32 }}
        >
          <span className="text-sm text-white">
            {bound ? (accountName?.[0]?.toUpperCase() ?? 'H') : '?'}
          </span>
          <span
            aria-hidden
            className={`absolute rounded-full ${bound ? 'bg-[#00ff88]' : 'bg-[#ffa502]'}`}
            style={{
              width: 5,
              height: 5,
              right: 0,
              bottom: 0,
              boxShadow: bound
                ? '0 0 0 3px rgba(10, 22, 40, 0.9)'
                : '0 0 0 3px rgba(10, 22, 40, 0.9)',
            }}
          />
        </button>

        {menuOpen && bound && (
          <div
            role="menu"
            className={`absolute left-0 z-20 min-w-[220px] rounded-lg bg-[#0f2137] border border-white/10 overflow-hidden ${
              popoverPlacement === 'top' ? 'bottom-full mb-1' : 'top-full mt-1'
            }`}
          >
            <div className="px-3 py-2 border-b border-white/10">
              <div className="text-sm text-white truncate">
                {accountName ?? t('account.name')}
              </div>
              {userUid && (
                <div className="text-xs text-[#6b7a9a] truncate">
                  uid {userUid}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onBind();
              }}
              className="block w-full text-left text-sm px-3 py-2 text-white hover:bg-white/10 transition-colors"
            >
              {t('rebind')}
            </button>
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                setConfirmUnbind(true);
              }}
              className="block w-full text-left text-sm px-3 py-2 text-[#ff4757] hover:bg-[#ff4757]/10 transition-colors"
            >
              {t('unbind')}
            </button>
          </div>
        )}

        {confirmUnbind && (
          <div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50"
            onClick={(e) => {
              e.stopPropagation();
              setConfirmUnbind(false);
            }}
          >
            <div
              role="dialog"
              aria-modal="true"
              className="w-[90%] max-w-md bg-[#0f2137] border border-white/10 rounded-xl p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between mb-3">
                <h2 className="text-lg font-semibold text-white">{t('confirmUnbind')}</h2>
                <button
                  type="button"
                  onClick={() => setConfirmUnbind(false)}
                  className="rounded-full p-1 text-[#6b7a9a] hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <p className="text-sm text-[#6b7a9a] mb-6">
                {t('confirmUnbindBody')}
              </p>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmUnbind(false)}
                  className="text-sm px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white hover:bg-white/10"
                >
                  {t('cancel')}
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      authApi.logout();
                    } catch (e) {
                      toast(t('unbindFail'), 'error');
                    } finally {
                      setConfirmUnbind(false);
                    }
                  }}
                  className="text-sm px-4 py-2 rounded-lg bg-[#ff4757] text-white hover:bg-[#ff4757]/90"
                >
                  {t('unbind')}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  },
);
