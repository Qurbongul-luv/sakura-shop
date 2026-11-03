import React, { useCallback, useEffect, useState } from 'react';
import { Check, RefreshCw, Send, XCircle } from 'lucide-react';
import { Order, OrderStatus, ShopSettings } from '../types';
import { Translations } from '../i18n';
import { EmptyState } from '../components/EmptyState';
import { formatPrice, getMediaUrl } from '../utils/format';
import { haptic, openTelegramLink } from '../utils/telegram';

interface OrdersPageProps {
  initData: string;
  settings: ShopSettings;
  onExplore: () => void;
  t: Translations;
}

type StepStatus = Exclude<OrderStatus, 'cancelled'>;

// Same order as the bot's STATUS_FLOW: statuses only move forward, steps may be skipped.
const STEPS: readonly StepStatus[] = ['new', 'accepted', 'purchased', 'shipping', 'arrived', 'delivered'];

const STEP_EMOJI: Record<OrderStatus, string> = {
  new: '🆕',
  accepted: '✅',
  purchased: '🛒',
  shipping: '✈️',
  arrived: '📍',
  delivered: '🎁',
  cancelled: '❌',
};

const stepLabel = (status: OrderStatus, t: Translations): string => {
  switch (status) {
    case 'new':
      return t.orderStepNew;
    case 'accepted':
      return t.orderStepAccepted;
    case 'purchased':
      return t.orderStepPurchased;
    case 'shipping':
      return t.orderStepShipping;
    case 'arrived':
      return t.orderStepArrived;
    case 'delivered':
      return t.orderStepDelivered;
    case 'cancelled':
      return t.orderStepCancelled;
  }
};

const formatDate = (iso?: string | null): string => {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const badgeClass = (status: OrderStatus): string => {
  if (status === 'cancelled') return 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-300';
  if (status === 'delivered') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300';
  return 'bg-sakura-blush text-sakura-darkrose dark:bg-sakura-darkcardsoft dark:text-sakura-pink';
};

const StatusTimeline: React.FC<{ status: StepStatus; t: Translations }> = ({ status, t }) => {
  const currentIndex = STEPS.indexOf(status);
  return (
    <ol className="mt-3 space-y-0">
      {STEPS.map((step, i) => {
        const done = i < currentIndex;
        const current = i === currentIndex;
        const isLast = i === STEPS.length - 1;
        return (
          <li key={step} className="flex gap-2.5">
            <div className="flex flex-col items-center">
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] shrink-0 ${
                  done
                    ? 'bg-sakura-rose text-white'
                    : current
                      ? 'bg-sakura-rose text-white ring-4 ring-sakura-pink/30'
                      : 'bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40'
                }`}
              >
                {done ? <Check className="w-3 h-3" /> : current ? STEP_EMOJI[step] : null}
              </div>
              {!isLast && (
                <div className={`w-0.5 flex-1 min-h-[14px] ${i < currentIndex ? 'bg-sakura-rose' : 'bg-sakura-pink/25'}`} />
              )}
            </div>
            <span
              className={`text-xs pb-2.5 leading-5 ${
                current
                  ? 'font-extrabold text-sakura-darkrose dark:text-sakura-pink'
                  : done
                    ? 'font-semibold text-sakura-plum dark:text-white'
                    : 'text-sakura-plum/45 dark:text-sakura-blush/45'
              }`}
            >
              {stepLabel(step, t)}
            </span>
          </li>
        );
      })}
    </ol>
  );
};

const OrderCard: React.FC<{ order: Order; contact: string; t: Translations }> = ({ order, contact, t }) => {
  const updated = order.status_updated_at ? formatDate(order.status_updated_at) : '';
  const askAdmin = () => {
    haptic.impact('light');
    const text = `🌸 ${t.orderLabel} #${order.id}\n`;
    openTelegramLink(`https://t.me/${contact}?text=${encodeURIComponent(text)}`);
  };

  return (
    <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm mb-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-black text-sakura-plum dark:text-white">
            {t.orderLabel} #{order.id}
          </div>
          <div className="text-[11px] text-sakura-plum/60 dark:text-sakura-blush/60">{formatDate(order.created_at)}</div>
        </div>
        <span className={`text-[11px] font-extrabold px-2.5 py-1 rounded-full whitespace-nowrap ${badgeClass(order.status)}`}>
          {STEP_EMOJI[order.status]} {stepLabel(order.status, t)}
        </span>
      </div>

      <div className="mt-3 space-y-2">
        {order.items_snapshot.map((item, idx) => (
          <div key={`${item.product_id}-${idx}`} className="flex items-center gap-2.5">
            <img
              src={getMediaUrl(item.photo)}
              alt=""
              loading="lazy"
              className="w-11 h-11 rounded-xl object-cover bg-sakura-cream dark:bg-sakura-darkcardsoft shrink-0"
            />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-sakura-plum dark:text-white truncate">{item.title}</div>
              <div className="text-[11px] text-sakura-plum/60 dark:text-sakura-blush/60 truncate">
                {[item.size, item.color].filter(Boolean).join(' · ')}
                {item.size || item.color ? ' · ' : ''}
                {item.qty} × {formatPrice(item.price)}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 pt-2 border-t border-sakura-pink/20 text-xs space-y-0.5">
        <div className="flex justify-between font-extrabold text-sakura-plum dark:text-white">
          <span>{t.grandTotal}</span>
          <span>{formatPrice(order.total)}</span>
        </div>
        {order.estimated_cargo > 0 && (
          <div className="flex justify-between text-sakura-plum/70 dark:text-sakura-blush/70">
            <span>{t.orderCargoEstimate}</span>
            <span>{formatPrice(order.estimated_cargo)}</span>
          </div>
        )}
      </div>

      {order.status === 'cancelled' ? (
        <div className="mt-3 flex items-start gap-2 p-2.5 rounded-2xl bg-red-50 dark:bg-red-900/20 text-[11px] text-red-600 dark:text-red-300">
          <XCircle className="w-4 h-4 shrink-0" />
          <span>{t.orderCancelledNote}</span>
        </div>
      ) : (
        <StatusTimeline status={order.status} t={t} />
      )}

      {updated && (
        <div className="text-[10px] text-sakura-plum/50 dark:text-sakura-blush/50 mt-1">
          {t.orderUpdatedAt}: {updated}
        </div>
      )}

      <button
        onClick={askAdmin}
        className="mt-3 w-full py-2.5 rounded-2xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/30 text-sakura-rose font-bold text-xs flex items-center justify-center gap-1.5 active:scale-95 transition-transform"
      >
        <Send className="w-3.5 h-3.5" />
        <span>{t.orderAskAdmin}</span>
      </button>
    </div>
  );
};

export const OrdersPage: React.FC<OrdersPageProps> = ({ initData, settings, onExplore, t }) => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState<boolean>(Boolean(initData));
  const [failed, setFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const contact = (settings.contact_username || 'fkhrdnvvvva').replace('@', '');

  useEffect(() => {
    if (!initData) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    fetch('/api/orders', { headers: { 'X-Telegram-Init-Data': initData }, signal: controller.signal })
      .then(async (resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data: unknown = await resp.json();
        setOrders(Array.isArray(data) ? (data as Order[]) : []);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        console.error('Error loading orders:', e);
        setFailed(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [initData, reloadKey]);

  const retry = useCallback(() => {
    haptic.selection();
    setReloadKey((k) => k + 1);
  }, []);

  return (
    <div className="pb-32 px-4 max-w-md mx-auto">
      <div className="py-3 flex items-center justify-between">
        <h2 className="text-lg font-black text-sakura-plum dark:text-white">{t.myOrders}</h2>
        {initData && !loading && (
          <button
            onClick={retry}
            aria-label={t.retry}
            className="p-2 rounded-xl text-sakura-rose active:scale-90 transition-transform"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <div key={i} className="h-40 rounded-3xl bg-white/60 dark:bg-sakura-darkcard/60 animate-pulse" />
          ))}
        </div>
      ) : failed ? (
        <div className="text-center py-10">
          <p className="text-sm font-bold text-sakura-plum dark:text-white mb-3">{t.myOrdersLoadError}</p>
          <button
            onClick={retry}
            className="px-6 py-2.5 rounded-2xl bg-gradient-to-r from-sakura-pink to-sakura-rose text-white font-semibold text-sm shadow-sakura active:scale-95 transition-transform"
          >
            {t.retry}
          </button>
        </div>
      ) : orders.length === 0 ? (
        <EmptyState
          title={t.myOrdersEmpty}
          subtitle={t.myOrdersEmptySubtitle}
          actionButton={{ text: t.continueShopping, onClick: onExplore }}
        />
      ) : (
        orders.map((order) => <OrderCard key={order.id} order={order} contact={contact} t={t} />)
      )}
    </div>
  );
};
