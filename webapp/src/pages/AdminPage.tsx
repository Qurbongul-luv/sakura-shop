import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Plus,
  Flame,
  Sparkles,
  Send,
  Upload,
  CheckCircle,
  XCircle,
  TrendingUp,
  Users,
  ShoppingBag,
  Clock,
  Eye,
  Heart,
  Edit2,
  Trash2,
  Share2,
  Gift,
  AlertTriangle,
  Search,
  Award,
  Ban,
  Check,
  Calendar,
  Folder,
  Star,
} from 'lucide-react';
import { Product, Category, Order, Review, AdminStats, Contest, LeaderboardEntry, SuspiciousUserItem } from '../types';
import { formatPrice, getMediaUrl } from '../utils/format';
import { haptic } from '../utils/telegram';
import { Translations } from '../i18n';

const PLACE_BADGES = ['🥇', '🥈', '🥉'];
const placeBadge = (index: number): string => PLACE_BADGES[index] ?? '🏅';

function contestPrizes(contest: Pick<Contest, 'prize_1' | 'prize_2' | 'prize_3' | 'prizes'>): string[] {
  return contest.prizes?.length ? contest.prizes : [contest.prize_1, contest.prize_2, contest.prize_3];
}

interface AdminPageProps {
  products: Product[];
  categories: Category[];
  initData: string;
  onRefreshProducts: () => void;
  onRefreshCategories?: () => void;
  onRefreshReviews?: () => void;
  t: Translations;
}

export const AdminPage: React.FC<AdminPageProps> = ({
  products,
  categories,
  initData,
  onRefreshProducts,
  onRefreshCategories,
  onRefreshReviews,
  t,
}) => {
  const [activeAdminSubTab, setActiveAdminSubTab] = useState<'products' | 'categories' | 'reviews' | 'orders' | 'contest' | 'stats' | 'broadcast'>('products');
  const [localCategories, setLocalCategories] = useState<Category[]>(categories);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [newCatName, setNewCatName] = useState('');
  const [newCatEmoji, setNewCatEmoji] = useState('🌸');
  const [newCatSlug, setNewCatSlug] = useState('');
  const [isSubmittingCat, setIsSubmittingCat] = useState(false);

  // Reviews Admin States
  const [reviewsList, setReviewsList] = useState<Review[]>([]);
  const [reviewsFilter, setReviewsFilter] = useState<'all' | 'pending' | 'approved'>('all');
  const [isLoadingReviews, setIsLoadingReviews] = useState(false);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Contest Admin States
  const [activeContest, setActiveContest] = useState<Contest | null>(null);
  const [contestLeaderboard, setContestLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [suspiciousUsers, setSuspiciousUsers] = useState<SuspiciousUserItem[]>([]);
  const [historyContests, setHistoryContests] = useState<any[]>([]);
  const [isContestModalOpen, setIsContestModalOpen] = useState(false);
  const [isEditPrizesModalOpen, setIsEditPrizesModalOpen] = useState(false);
  const [userCheckQuery, setUserCheckQuery] = useState('');
  const [userCheckData, setUserCheckData] = useState<any | null>(null);

  // New Contest Form
  const [cPrize1, setCPrize1] = useState('');
  const [cPrize2, setCPrize2] = useState('');
  const [cPrize3, setCPrize3] = useState('');
  const [cDurationDays, setCDurationDays] = useState(7);
  const [cOnlyNewSubscribers, setCOnlyNewSubscribers] = useState(true);
  const [isCreatingContest, setIsCreatingContest] = useState(false);

  // Edit Prizes Form
  const [editP1, setEditP1] = useState('');
  const [editP2, setEditP2] = useState('');
  const [editP3, setEditP3] = useState('');

  // Form states for Add/Edit Product
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('');
  const [oldPrice, setOldPrice] = useState('');
  const [category, setCategory] = useState('jempir');
  const [sizes, setSizes] = useState('');
  const [colors, setColors] = useState('');
  const [weightGrams, setWeightGrams] = useState('');
  const [photos, setPhotos] = useState<string[]>([]);
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Broadcast state
  const [broadcastText, setBroadcastText] = useState('');
  const [isBroadcasting, setIsBroadcasting] = useState(false);
  const [broadcastStatus, setBroadcastStatus] = useState<string | null>(null);

  // Keep local categories in sync with props
  useEffect(() => {
    setLocalCategories(categories);
  }, [categories]);

  // Load reviews when tab changes
  useEffect(() => {
    if (activeAdminSubTab === 'reviews') {
      fetchAdminReviews();
    }
  }, [activeAdminSubTab, initData]);

  // Load stats, orders, contest data
  useEffect(() => {
    fetchStats();
    fetchOrders();
    fetchContestAdminData();
  }, [initData, activeAdminSubTab]);

  const fetchContestAdminData = async () => {
    try {
      const headers = { 'X-Telegram-Init-Data': initData };
      const resp = await fetch('/api/contest/active', { headers });
      if (resp.ok) {
        const data = await resp.json();
        setActiveContest(data.has_active_contest ? data.contest : null);
        if (data.has_active_contest && data.contest) {
          setEditP1(data.contest.prize_1);
          setEditP2(data.contest.prize_2);
          setEditP3(data.contest.prize_3);

          const bResp = await fetch('/api/contest/leaderboard?limit=20');
          if (bResp.ok) setContestLeaderboard(await bResp.json());

          const sResp = await fetch('/api/admin/contest/suspicious', { headers });
          if (sResp.ok) setSuspiciousUsers(await sResp.json());
        }
      }

      const hResp = await fetch('/api/admin/contest/history', { headers });
      if (hResp.ok) setHistoryContests(await hResp.json());
    } catch (e) {
      console.error('Error loading contest admin data:', e);
    }
  };

  const handleCreateContest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cPrize1.trim() || !cPrize2.trim() || !cPrize3.trim()) {
      alert("Iltimos, barcha 3 ta sovg'ani kiriting!");
      return;
    }
    setIsCreatingContest(true);
    haptic.impact('heavy');

    const endsAt = new Date();
    endsAt.setDate(endsAt.getDate() + cDurationDays);

    try {
      const resp = await fetch('/api/admin/contest/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({
          prize_1: cPrize1.trim(),
          prize_2: cPrize2.trim(),
          prize_3: cPrize3.trim(),
          ends_at: endsAt.toISOString(),
          only_new_subscribers: cOnlyNewSubscribers,
        }),
      });

      if (resp.ok) {
        setIsContestModalOpen(false);
        setCPrize1('');
        setCPrize2('');
        setCPrize3('');
        fetchContestAdminData();
        haptic.notification('success');
      } else {
        const err = await resp.json();
        alert(err.detail || 'Xatolik yuz berdi');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsCreatingContest(false);
    }
  };

  const handleExtendContest = async (days: number) => {
    haptic.impact('medium');
    try {
      const resp = await fetch('/api/admin/contest/extend', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ additional_days: days }),
      });
      if (resp.ok) {
        fetchContestAdminData();
        haptic.notification('success');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdatePrizes = async (e: React.FormEvent) => {
    e.preventDefault();
    haptic.impact('medium');
    try {
      const resp = await fetch('/api/admin/contest/prizes', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({
          prize_1: editP1.trim(),
          prize_2: editP2.trim(),
          prize_3: editP3.trim(),
        }),
      });
      if (resp.ok) {
        setIsEditPrizesModalOpen(false);
        fetchContestAdminData();
        haptic.notification('success');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleEndContestNow = async () => {
    if (!window.confirm("Haqiqatan ham konkursni hozir yakunlamoqchimisiz? Natijalar hisoblanadi.")) return;
    haptic.impact('heavy');
    try {
      const resp = await fetch('/api/admin/contest/end-now', {
        method: 'POST',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        fetchContestAdminData();
        haptic.notification('success');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCancelContest = async () => {
    if (!window.confirm("DIQQAT: Konkursni bekor qilsangiz, hech kim yutmaydi. Tasdiqlaysizmi?")) return;
    haptic.impact('heavy');
    try {
      const resp = await fetch('/api/admin/contest/cancel', {
        method: 'POST',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        fetchContestAdminData();
        haptic.notification('warning');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleApproveContestResults = async () => {
    haptic.impact('heavy');
    try {
      const resp = await fetch('/api/admin/contest/approve-results', {
        method: 'POST',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        fetchContestAdminData();
        haptic.notification('success');
        alert("G'oliblar kanalga e'lon qilindi va xabarlar yuborildi! 🌸");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSearchUser = async () => {
    if (!userCheckQuery.trim()) return;
    try {
      const resp = await fetch(`/api/admin/contest/user-check/${encodeURIComponent(userCheckQuery.trim())}`, {
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        setUserCheckData(await resp.json());
      } else {
        alert("Foydalanuvchi topilmadi yoki bu ID bo'yicha ma'lumot yo'q.");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDisqualifyUser = async (userId: number) => {
    const reason = prompt("Diskvalifikatsiya sababi:", "Qoidabuzarlik");
    if (!reason) return;
    try {
      const resp = await fetch('/api/admin/contest/disqualify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ user_id: userId, reason }),
      });
      if (resp.ok) {
        fetchContestAdminData();
        if (userCheckData) handleSearchUser();
        haptic.notification('success');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchStats = async () => {
    try {
      const resp = await fetch('/api/admin/stats', {
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        setStats(await resp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchOrders = async () => {
    try {
      const resp = await fetch('/api/admin/orders', {
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        setOrders(await resp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCatName.trim()) return;
    setIsSubmittingCat(true);
    haptic.impact('medium');

    const cleanSlug = (newCatSlug.trim() || newCatName.trim().toLowerCase().replace(/[^a-z0-9]/g, '-')).replace(/^-+|-+$/g, '');
    try {
      const resp = await fetch('/api/admin/categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({
          name: newCatName.trim(),
          emoji: newCatEmoji.trim() || '🌸',
          slug: cleanSlug,
          sort_order: localCategories.length,
        }),
      });

      if (resp.ok) {
        setIsCategoryModalOpen(false);
        setNewCatName('');
        setNewCatEmoji('🌸');
        setNewCatSlug('');
        onRefreshCategories?.();
        haptic.notification('success');
      } else {
        const err = await resp.json();
        alert(err.detail || "Xatolik yuz berdi");
      }
    } catch (e) {
      console.error(e);
      alert("Bo'lim qo'shishda xatolik");
    } finally {
      setIsSubmittingCat(false);
    }
  };

  const handleDeleteCategory = async (slug: string, count: number) => {
    const confirmMsg = count > 0
      ? `Bu bo'limda ${count} ta mahsulot bor. Bo'lim va undagi barcha mahsulotlar o'chirilsinmi?`
      : `Haqiqatan ham '#${slug}' bo'limini o'chirib tashlamoqchimisiz?`;
    if (!window.confirm(confirmMsg)) return;

    haptic.impact('heavy');
    try {
      const resp = await fetch(`/api/admin/categories/${encodeURIComponent(slug)}?force=true`, {
        method: 'DELETE',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        onRefreshCategories?.();
        onRefreshProducts();
        haptic.notification('success');
      } else {
        const err = await resp.json();
        alert(err.detail || "O'chirishda xatolik yuz berdi");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAdminReviews = async () => {
    setIsLoadingReviews(true);
    try {
      const resp = await fetch('/api/admin/reviews', {
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        setReviewsList(await resp.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoadingReviews(false);
    }
  };

  const handleDeleteReview = async (reviewId: number) => {
    if (!window.confirm("Haqiqatan ham bu fikrni o'chirib tashlamoqchimisiz?")) return;
    haptic.impact('heavy');
    try {
      const resp = await fetch(`/api/admin/reviews/${reviewId}`, {
        method: 'DELETE',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        setReviewsList((prev) => prev.filter((r) => r.id !== reviewId));
        onRefreshReviews?.();
        haptic.notification('success');
      } else {
        alert("Fikrni o'chirishda xatolik");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleApproveReview = async (review: Review) => {
    haptic.impact('light');
    try {
      const resp = await fetch(`/api/admin/reviews/${review.id}/approve?approved=${!review.approved}`, {
        method: 'PATCH',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        const updated = await resp.json();
        setReviewsList((prev) => prev.map((r) => (r.id === review.id ? updated : r)));
        onRefreshReviews?.();
        haptic.notification('success');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleStock = async (product: Product) => {
    haptic.impact('light');
    try {
      const resp = await fetch(`/api/admin/products/${product.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ in_stock: !product.in_stock }),
      });
      if (resp.ok) {
        onRefreshProducts();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handlePostToChannel = async (productId: number) => {
    haptic.impact('medium');
    try {
      const resp = await fetch(`/api/admin/products/${productId}/post-to-channel`, {
        method: 'POST',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      const data = await resp.json();
      if (data.success) {
        alert("✅ Mahsulot kanalga muvaffaqiyatli joylandi! 🌸");
      } else {
        alert(`⚠️ Xatolik: ${data.error}`);
      }
    } catch (e) {
      alert("Kanalga joylashda xatolik yuz berdi.");
    }
  };

  const handleDeleteProduct = async (productId: number) => {
    if (!confirm(t.confirmDelete)) return;
    haptic.notification('warning');
    try {
      const resp = await fetch(`/api/admin/products/${productId}`, {
        method: 'DELETE',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        onRefreshProducts();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingPhoto(true);
    haptic.impact('light');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await fetch('/api/admin/upload-photo', {
        method: 'POST',
        headers: { 'X-Telegram-Init-Data': initData },
        body: formData,
      });

      if (resp.ok) {
        const data = await resp.json();
        setPhotos((prev) => [...prev, data.file_id]);
        haptic.notification('success');
      } else {
        alert("Rasm yuklashda xatolik yuz berdi.");
      }
    } catch (err) {
      console.error(err);
      alert("Rasm yuklab bo'lmadi.");
    } finally {
      setIsUploadingPhoto(false);
    }
  };

  const openAddModal = () => {
    setEditingProduct(null);
    setTitle('');
    setDescription('');
    setPrice('');
    setOldPrice('');
    setCategory(categories[0]?.slug || 'jempir');
    setSizes('');
    setColors('');
    setWeightGrams('');
    setPhotos([]);
    setIsProductModalOpen(true);
  };

  const openEditModal = (p: Product) => {
    setEditingProduct(p);
    setTitle(p.title);
    setDescription(p.description || '');
    setPrice(p.price.toString());
    setOldPrice(p.old_price ? p.old_price.toString() : '');
    setCategory(p.category);
    setSizes(p.sizes?.join(', ') || '');
    setColors(p.colors?.join(', ') || '');
    setWeightGrams(p.weight_grams ? p.weight_grams.toString() : '');
    setPhotos(p.photos || []);
    setIsProductModalOpen(true);
  };

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !price.trim()) return;

    setIsSubmitting(true);
    haptic.impact('medium');

    const payload = {
      title: title.trim(),
      description: description.trim(),
      price: parseInt(price.replace(/\D/g, '') || '0'),
      old_price: oldPrice ? parseInt(oldPrice.replace(/\D/g, '') || '0') : null,
      category: category,
      photos: photos,
      sizes: sizes ? sizes.split(',').map((s) => s.trim()).filter(Boolean) : [],
      colors: colors ? colors.split(',').map((c) => c.trim()).filter(Boolean) : [],
      weight_grams: weightGrams ? parseInt(weightGrams.replace(/\D/g, '') || '0') : null,
      in_stock: true,
    };

    try {
      const url = editingProduct ? `/api/admin/products/${editingProduct.id}` : '/api/admin/products';
      const method = editingProduct ? 'PUT' : 'POST';

      const resp = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify(payload),
      });

      if (resp.ok) {
        setIsProductModalOpen(false);
        onRefreshProducts();
        haptic.notification('success');
      }
    } catch (e) {
      console.error(e);
      alert("Saqlashda xatolik yuz berdi.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateOrderStatus = async (orderId: number, newStatus: string) => {
    haptic.impact('medium');
    try {
      const resp = await fetch(`/api/admin/orders/${orderId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ status: newStatus }),
      });
      if (resp.ok) {
        fetchOrders();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendBroadcast = async () => {
    if (!broadcastText.trim()) return;
    setIsBroadcasting(true);
    haptic.impact('heavy');

    try {
      const resp = await fetch('/api/admin/broadcast', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ text: broadcastText.trim() }),
      });
      if (resp.ok) {
        setBroadcastStatus("✅ Xabar tarqatish bot orqali boshlandi!");
        setBroadcastText('');
        setTimeout(() => setBroadcastStatus(null), 4000);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsBroadcasting(false);
    }
  };

  return (
    <div className="pb-32 px-4 max-w-md mx-auto">
      {/* Title */}
      <div className="py-3 flex items-center justify-between">
        <h2 className="text-lg font-black text-sakura-plum dark:text-white flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-sakura-rose" />
          <span>{t.adminDashboard}</span>
        </h2>
        <span className="text-[11px] font-bold text-white bg-sakura-rose px-2.5 py-0.5 rounded-full">
          Super Admin 🌸
        </span>
      </div>

      {/* Admin Subtabs */}
      <div className="flex bg-white/80 dark:bg-sakura-darkcard/80 p-1 rounded-2xl border border-sakura-pink/30 mb-4 shadow-xs overflow-x-auto gap-1">
        <button
          onClick={() => setActiveAdminSubTab('products')}
          className={`px-3 py-1.5 text-[11px] font-bold rounded-xl transition-all whitespace-nowrap ${
            activeAdminSubTab === 'products'
              ? 'bg-sakura-rose text-white shadow-sm'
              : 'text-sakura-plum/70 dark:text-sakura-blush/70'
          }`}
        >
          Mahsulotlar
        </button>
        <button
          onClick={() => setActiveAdminSubTab('categories')}
          className={`px-3 py-1.5 text-[11px] font-bold rounded-xl transition-all whitespace-nowrap ${
            activeAdminSubTab === 'categories'
              ? 'bg-sakura-rose text-white shadow-sm'
              : 'text-sakura-plum/70 dark:text-sakura-blush/70'
          }`}
        >
          🗂 Bo'limlar ({localCategories.length})
        </button>
        <button
          onClick={() => setActiveAdminSubTab('reviews')}
          className={`px-3 py-1.5 text-[11px] font-bold rounded-xl transition-all whitespace-nowrap ${
            activeAdminSubTab === 'reviews'
              ? 'bg-sakura-rose text-white shadow-sm'
              : 'text-sakura-plum/70 dark:text-sakura-blush/70'
          }`}
        >
          ⭐ Fikrlar ({reviewsList.length})
        </button>
        <button
          onClick={() => setActiveAdminSubTab('orders')}
          className={`px-3 py-1.5 text-[11px] font-bold rounded-xl transition-all whitespace-nowrap ${
            activeAdminSubTab === 'orders'
              ? 'bg-sakura-rose text-white shadow-sm'
              : 'text-sakura-plum/70 dark:text-sakura-blush/70'
          }`}
        >
          Buyurtmalar ({orders.filter((o) => o.status === 'new').length})
        </button>
        <button
          onClick={() => setActiveAdminSubTab('contest')}
          className={`px-3 py-1.5 text-[11px] font-bold rounded-xl transition-all whitespace-nowrap flex items-center gap-1 ${
            activeAdminSubTab === 'contest'
              ? 'bg-sakura-rose text-white shadow-sm'
              : 'text-sakura-plum/70 dark:text-sakura-blush/70'
          }`}
        >
          <Gift className="w-3.5 h-3.5" />
          <span>Konkurs</span>
        </button>
        <button
          onClick={() => setActiveAdminSubTab('stats')}
          className={`px-3 py-1.5 text-[11px] font-bold rounded-xl transition-all whitespace-nowrap ${
            activeAdminSubTab === 'stats'
              ? 'bg-sakura-rose text-white shadow-sm'
              : 'text-sakura-plum/70 dark:text-sakura-blush/70'
          }`}
        >
          Statistika
        </button>
        <button
          onClick={() => setActiveAdminSubTab('broadcast')}
          className={`px-3 py-1.5 text-[11px] font-bold rounded-xl transition-all whitespace-nowrap ${
            activeAdminSubTab === 'broadcast'
              ? 'bg-sakura-rose text-white shadow-sm'
              : 'text-sakura-plum/70 dark:text-sakura-blush/70'
          }`}
        >
          Tarqatish
        </button>
      </div>

      {/* ================= PRODUCTS TAB ================= */}
      {activeAdminSubTab === 'products' && (
        <div>
          <button
            onClick={openAddModal}
            className="w-full py-3 mb-4 rounded-2xl bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white font-black text-xs flex items-center justify-center gap-2 shadow-sakura active:scale-98 transition-transform"
          >
            <Plus className="w-4 h-4" />
            <span>{t.addNewProduct}</span>
          </button>

          <div className="flex flex-col gap-2.5">
            {products.map((p) => (
              <div
                key={p.id}
                className="p-3 rounded-2xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-xs flex items-center gap-3"
              >
                <div className="w-14 h-14 rounded-xl overflow-hidden shrink-0 bg-sakura-blush">
                  <img src={getMediaUrl(p.photos?.[0])} alt="" className="w-full h-full object-cover" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-bold text-sakura-rose uppercase">#{p.category}</span>
                    <span className="text-xs font-bold truncate">{p.title}</span>
                  </div>
                  <span className="text-xs font-black text-sakura-rose block mt-0.5">
                    {formatPrice(p.price)}
                  </span>
                </div>

                {/* Quick Stock Toggle */}
                <button
                  onClick={() => handleToggleStock(p)}
                  className={`px-2.5 py-1 rounded-xl text-[10px] font-extrabold whitespace-nowrap active:scale-90 transition-transform ${
                    p.in_stock
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                      : 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-400'
                  }`}
                >
                  {p.in_stock ? 'Mavjud ✅' : 'Sotildi ❌'}
                </button>

                {/* Actions: Post to Channel / Edit / Delete */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handlePostToChannel(p.id)}
                    title="Kanalga joylash"
                    className="p-1.5 rounded-lg text-sakura-plum/60 hover:text-sakura-rose"
                  >
                    <Share2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => openEditModal(p)}
                    title="Tahrirlash"
                    className="p-1.5 rounded-lg text-sakura-plum/60 hover:text-sakura-rose"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteProduct(p.id)}
                    title="O'chirish"
                    className="p-1.5 rounded-lg text-sakura-plum/60 hover:text-rose-500"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ================= CATEGORIES TAB ================= */}
      {activeAdminSubTab === 'categories' && (
        <div>
          <button
            onClick={() => setIsCategoryModalOpen(true)}
            className="w-full py-3 mb-4 rounded-2xl bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white font-black text-xs flex items-center justify-center gap-2 shadow-sakura active:scale-98 transition-transform"
          >
            <Plus className="w-4 h-4" />
            <span>➕ Yangi bo'lim (kategoriya) qo'shish</span>
          </button>

          <div className="flex flex-col gap-2.5">
            {localCategories.map((c) => (
              <div
                key={c.slug}
                className="p-3.5 rounded-2xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-xs flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-11 h-11 rounded-2xl bg-sakura-blush/80 dark:bg-sakura-darkcardsoft flex items-center justify-center text-xl shrink-0 border border-sakura-pink/30">
                    {c.emoji || '🌸'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-extrabold text-sm text-sakura-plum dark:text-white truncate">
                        {c.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] font-bold text-sakura-rose">#{c.slug}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-sakura-pink/20 text-sakura-darkrose dark:text-sakura-pink font-extrabold">
                        {c.product_count || 0} ta mahsulot
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleDeleteCategory(c.slug, c.product_count || 0)}
                  title="Bo'limni o'chirish"
                  className="p-2.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-600 dark:bg-rose-950/40 dark:text-rose-400 active:scale-90 transition-transform shrink-0"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ================= REVIEWS TAB ================= */}
      {activeAdminSubTab === 'reviews' && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-extrabold text-sakura-plum dark:text-white">
              Jami fikrlar: {reviewsList.length} ta
            </span>
            <div className="flex gap-1 bg-white/70 dark:bg-sakura-darkcard p-0.5 rounded-xl border border-sakura-pink/20">
              <button
                onClick={() => setReviewsFilter('all')}
                className={`px-2.5 py-1 text-[10px] font-bold rounded-lg ${
                  reviewsFilter === 'all' ? 'bg-sakura-rose text-white' : 'text-sakura-plum/60'
                }`}
              >
                Barchasi
              </button>
              <button
                onClick={() => setReviewsFilter('pending')}
                className={`px-2.5 py-1 text-[10px] font-bold rounded-lg ${
                  reviewsFilter === 'pending' ? 'bg-sakura-rose text-white' : 'text-sakura-plum/60'
                }`}
              >
                Kutilmoqda
              </button>
              <button
                onClick={() => setReviewsFilter('approved')}
                className={`px-2.5 py-1 text-[10px] font-bold rounded-lg ${
                  reviewsFilter === 'approved' ? 'bg-sakura-rose text-white' : 'text-sakura-plum/60'
                }`}
              >
                Tasdiqlangan
              </button>
            </div>
          </div>

          {isLoadingReviews ? (
            <div className="py-8 text-center text-xs font-bold text-sakura-plum/50">
              Fikrlar yuklanmoqda... 🌸
            </div>
          ) : reviewsList.length === 0 ? (
            <div className="py-12 text-center rounded-2xl bg-white/60 dark:bg-sakura-darkcard/60 border border-dashed border-sakura-pink/30 p-4">
              <Star className="w-8 h-8 text-sakura-rose/40 mx-auto mb-2" />
              <p className="text-xs font-bold text-sakura-plum/60 dark:text-sakura-blush/60">
                Hozircha birorta ham mijoz fikri yo'q
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {reviewsList
                .filter((r) => {
                  if (reviewsFilter === 'pending') return !r.approved;
                  if (reviewsFilter === 'approved') return r.approved;
                  return true;
                })
                .map((r) => (
                  <div
                    key={r.id}
                    className="p-3.5 rounded-2xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-xs"
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-extrabold text-xs text-sakura-plum dark:text-white">
                            {r.customer_name || 'Mijoz'}
                          </span>
                          <span
                            className={`text-[9px] px-2 py-0.5 rounded-full font-extrabold ${
                              r.approved
                                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                                : 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400'
                            }`}
                          >
                            {r.approved ? 'Tasdiqlangan ✅' : 'Kutilmoqda ⏳'}
                          </span>
                        </div>
                        <span className="text-[10px] text-sakura-plum/40 dark:text-sakura-blush/40 block mt-0.5">
                          {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                        </span>
                      </div>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleToggleApproveReview(r)}
                          title={r.approved ? "Yashirish" : "Tasdiqlash"}
                          className={`p-1.5 rounded-xl active:scale-90 transition-transform ${
                            r.approved
                              ? 'bg-amber-50 text-amber-600 hover:bg-amber-100'
                              : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
                          }`}
                        >
                          {r.approved ? <Ban className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                        </button>
                        <button
                          onClick={() => handleDeleteReview(r.id)}
                          title="Fikrni o'chirish"
                          className="p-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-600 active:scale-90 transition-transform"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <p className="text-xs font-medium text-sakura-plum/80 dark:text-sakura-blush/80 leading-relaxed bg-sakura-bg/40 dark:bg-sakura-darkcardsoft p-2.5 rounded-xl">
                      "{r.text}"
                    </p>

                    {r.photos && r.photos.length > 0 && (
                      <div className="flex gap-2 mt-2.5 overflow-x-auto pb-1">
                        {r.photos.map((ph, idx) => (
                          <img
                            key={idx}
                            src={getMediaUrl(ph)}
                            alt=""
                            className="w-14 h-14 rounded-xl object-cover shrink-0 border border-sakura-pink/20"
                          />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {/* ================= ORDERS TAB ================= */}
      {activeAdminSubTab === 'orders' && (
        <div className="flex flex-col gap-3">
          {orders.length === 0 ? (
            <p className="text-xs text-center py-8 text-sakura-plum/60">Hozircha buyurtmalar yo'q.</p>
          ) : (
            orders.map((o) => (
              <div
                key={o.id}
                className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm"
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="font-extrabold text-sm block">Buyurtma #{o.id}</span>
                    <span className="text-[11px] text-sakura-plum/70 dark:text-sakura-blush/70">
                      Mijoz: {o.customer_name} ({o.customer_username ? `@${o.customer_username}` : 'No username'})
                    </span>
                  </div>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase ${
                      o.status === 'accepted'
                        ? 'bg-emerald-100 text-emerald-700'
                        : o.status === 'cancelled'
                        ? 'bg-rose-100 text-rose-700'
                        : 'bg-amber-100 text-amber-700 animate-pulse'
                    }`}
                  >
                    {o.status}
                  </span>
                </div>

                <div className="text-xs space-y-1 py-1.5 border-y border-sakura-pink/20 my-2">
                  {o.items_snapshot.map((it, idx) => (
                    <div key={idx} className="flex justify-between text-sakura-plum/80 dark:text-sakura-blush/80">
                      <span>
                        {idx + 1}. {it.title} ({it.qty} dona) {it.size ? `[${it.size}]` : ''}
                      </span>
                      <span className="font-bold">{formatPrice(it.price * it.qty)}</span>
                    </div>
                  ))}
                </div>

                <div className="flex justify-between items-center mt-2">
                  <div>
                    <span className="text-xs font-black text-sakura-rose">
                      Jami: {formatPrice(o.total)}
                    </span>
                    {o.estimated_cargo > 0 && (
                      <span className="text-[10px] text-sakura-plum/60 block">
                        + Kargo: {formatPrice(o.estimated_cargo)}
                      </span>
                    )}
                  </div>

                  {o.status === 'new' && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleUpdateOrderStatus(o.id, 'accepted')}
                        className="px-3 py-1 rounded-xl bg-emerald-500 text-white font-bold text-xs shadow-xs"
                      >
                        Qabul ✅
                      </button>
                      <button
                        onClick={() => handleUpdateOrderStatus(o.id, 'cancelled')}
                        className="px-3 py-1 rounded-xl bg-rose-500 text-white font-bold text-xs shadow-xs"
                      >
                        Bekor ❌
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ================= CONTEST TAB ================= */}
      {activeAdminSubTab === 'contest' && (
        <div className="flex flex-col gap-3">
          {activeContest ? (
            <>
              {/* Active Contest Status Card */}
              <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 border border-sakura-pink/30 shadow-sakura-sm">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Gift className="w-5 h-5 text-sakura-rose animate-bounce" />
                    <div>
                      <h4 className="text-sm font-black text-sakura-plum dark:text-white">
                        Konkurs #{activeContest.id}
                      </h4>
                      <span className="text-[10px] text-sakura-plum/60">
                        {activeContest.only_new_subscribers ? "🔒 Faqat yangi obunachilar" : "🔓 Barcha a'zolar"}
                      </span>
                    </div>
                  </div>
                  <span
                    className={`px-3 py-1 rounded-full text-[11px] font-black ${
                      activeContest.status === 'active'
                        ? 'bg-emerald-100 text-emerald-700 animate-pulse'
                        : 'bg-amber-100 text-amber-700'
                    }`}
                  >
                    {activeContest.status === 'active' ? 'Faol 🟢' : 'Yakunlangan 🟡'}
                  </span>
                </div>

                {/* Prizes Display */}
                <div className="bg-sakura-blush/40 dark:bg-sakura-darkcardsoft/50 rounded-2xl p-3 my-2 space-y-1.5 text-xs">
                  {contestPrizes(activeContest).map((prize, index) => (
                    <div key={index} className="flex items-center justify-between">
                      <span className="font-bold flex items-center gap-1.5">
                        <span>{placeBadge(index)} {index + 1}-o'rin:</span>
                        <span className="text-sakura-rose font-black">{prize}</span>
                      </span>
                    </div>
                  ))}
                  <button
                    onClick={() => setIsEditPrizesModalOpen(true)}
                    className="w-full mt-2 py-1.5 rounded-xl border border-sakura-pink/40 text-[11px] font-bold text-sakura-rose bg-white dark:bg-sakura-darkcard"
                  >
                    ✏️ Sovg'alarni o'zgartirish
                  </button>
                </div>

                {/* Action buttons */}
                <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                  <button
                    onClick={() => handleExtendContest(1)}
                    className="py-2 px-2 rounded-xl bg-pink-100 text-pink-700 dark:bg-pink-950/60 dark:text-pink-300 font-bold text-[11px]"
                  >
                    ➕ 1 kun uzaytirish
                  </button>
                  <button
                    onClick={() => handleExtendContest(3)}
                    className="py-2 px-2 rounded-xl bg-pink-100 text-pink-700 dark:bg-pink-950/60 dark:text-pink-300 font-bold text-[11px]"
                  >
                    ➕ 3 kun uzaytirish
                  </button>
                  <button
                    onClick={handleEndContestNow}
                    className="py-2 px-2 rounded-xl bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 font-bold text-[11px]"
                  >
                    🛑 Hozir tugatish
                  </button>
                  <button
                    onClick={handleCancelContest}
                    className="py-2 px-2 rounded-xl bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 font-bold text-[11px]"
                  >
                    ❌ Bekor qilish
                  </button>
                </div>

                {activeContest.status === 'ended' && (
                  <button
                    onClick={handleApproveContestResults}
                    className="w-full mt-3 py-3 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-black text-xs shadow-lg animate-pulse"
                  >
                    🏆 G'oliblarni tasdiqlash va e'lon qilish
                  </button>
                )}
              </div>

              {/* Suspicious Activity Warning */}
              {suspiciousUsers.length > 0 && (
                <div className="p-4 rounded-3xl bg-rose-50 dark:bg-rose-950/30 border border-rose-300 dark:border-rose-800">
                  <div className="flex items-center gap-2 mb-2 text-rose-600 font-black text-xs">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Shubhali harakatlar ({suspiciousUsers.length} ta)</span>
                  </div>
                  <p className="text-[10px] text-rose-700/80 mb-2">
                    Ushbu ishtirokchilar taklif qilgan odamlarning 40% dan ortig'i kanaldan chiqib ketgan:
                  </p>
                  <div className="space-y-1.5">
                    {suspiciousUsers.map((su) => (
                      <div
                        key={su.referrer_id}
                        className="flex items-center justify-between bg-white/80 dark:bg-sakura-darkcard/80 p-2 rounded-xl text-[11px]"
                      >
                        <div>
                          <span className="font-bold">
                            {su.name || `ID ${su.referrer_id}`}
                          </span>
                          <span className="text-[9px] text-rose-500 block">
                            Chiqib ketgan: {su.revoked_invites} ta ({(su.revoked_ratio * 100).toFixed(0)}%)
                          </span>
                        </div>
                        <button
                          onClick={() => handleDisqualifyUser(su.referrer_id)}
                          className="px-2 py-1 bg-rose-500 text-white text-[10px] font-bold rounded-lg shadow-xs"
                        >
                          Diskvalifikatsiya 🚫
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* User Check & Audit Search Box */}
              <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 border border-sakura-pink/30 shadow-sakura-sm">
                <h4 className="text-xs font-black text-sakura-plum dark:text-white mb-2 flex items-center gap-1.5">
                  <Search className="w-4 h-4 text-sakura-rose" />
                  <span>Ishtirokchini tekshirish / diskvalifikatsiya</span>
                </h4>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={userCheckQuery}
                    onChange={(e) => setUserCheckQuery(e.target.value)}
                    placeholder="Telegram ID kiriting (masalan: 12345678)"
                    className="flex-1 p-2 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 text-xs"
                  />
                  <button
                    onClick={handleSearchUser}
                    className="px-3 py-2 bg-sakura-rose text-white font-bold text-xs rounded-xl shadow-xs"
                  >
                    Tekshirish
                  </button>
                </div>

                {userCheckData && (
                  <div className="bg-sakura-blush/30 dark:bg-sakura-darkcardsoft/40 p-3 rounded-2xl text-xs space-y-1 mt-2">
                    <div className="flex justify-between font-bold">
                      <span>Ishtirokchi:</span>
                      <span>{userCheckData.user?.first_name || userCheckData.user_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Ball (tasdiqlangan):</span>
                      <span className="font-black text-emerald-600">{userCheckData.confirmed_count} ta</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Chiqib ketgan:</span>
                      <span className="font-bold text-rose-500">{userCheckData.revoked_count} ta</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Kutilmoqda:</span>
                      <span>{userCheckData.pending_count} ta</span>
                    </div>
                    <button
                      onClick={() => handleDisqualifyUser(userCheckData.user_id)}
                      className="w-full mt-2 py-1.5 bg-rose-500 text-white font-bold text-xs rounded-xl shadow-xs"
                    >
                      Ushbu foydalanuvchini diskvalifikatsiya qilish 🚫
                    </button>
                  </div>
                )}
              </div>

              {/* Leaderboard Table */}
              <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 border border-sakura-pink/30 shadow-sakura-sm">
                <h4 className="text-xs font-black text-sakura-plum dark:text-white mb-2 flex items-center gap-1.5">
                  <Award className="w-4 h-4 text-sakura-rose" />
                  <span>Joriy peshqadamlar jadvali</span>
                </h4>
                <div className="space-y-1">
                  {contestLeaderboard.length === 0 ? (
                    <p className="text-[11px] text-center text-sakura-plum/60 py-3">
                      Hozircha ball to'plagan ishtirokchilar yo'q.
                    </p>
                  ) : (
                    contestLeaderboard.map((entry) => (
                      <div
                        key={entry.user_id}
                        className="flex items-center justify-between text-xs py-1.5 px-2 rounded-xl bg-sakura-cream/50 dark:bg-sakura-darkcardsoft/40"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-black w-5 text-sakura-rose">#{entry.rank}</span>
                          <span className="font-bold truncate max-w-[140px]">
                            {entry.name || `ID ${entry.user_id}`}
                            {entry.username && ` (@${entry.username})`}
                          </span>
                        </div>
                        <span className="font-black text-sakura-rose">
                          {entry.score} ball
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          ) : (
            /* No Active Contest */
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-3 rounded-full bg-sakura-blush flex items-center justify-center text-sakura-rose text-2xl">
                🌸
              </div>
              <h3 className="font-black text-base text-sakura-plum dark:text-white mb-1">
                Faol konkurs mavjud emas
              </h3>
              <p className="text-xs text-sakura-plum/70 dark:text-sakura-blush/70 mb-4 max-w-xs mx-auto">
                Kanal obunachilarini ko'paytirish va faollikni oshirish uchun yangi konkurs boshlang!
              </p>
              <button
                onClick={() => setIsContestModalOpen(true)}
                className="py-3 px-6 rounded-2xl bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white font-black text-xs shadow-sakura active:scale-95 transition-transform"
              >
                🎁 Yangi konkurs yaratish
              </button>

              {/* History Contests */}
              {historyContests.length > 0 && (
                <div className="mt-8 text-left">
                  <h4 className="text-xs font-black text-sakura-plum dark:text-white mb-2">
                    Avvalgi konkurslar tarixi:
                  </h4>
                  <div className="space-y-2">
                    {historyContests.map((hc) => (
                      <div
                        key={hc.id}
                        className="p-3 rounded-2xl bg-white/80 dark:bg-sakura-darkcard/80 border border-sakura-pink/20 text-xs"
                      >
                        <div className="flex justify-between items-center mb-1">
                          <span className="font-bold">Konkurs #{hc.id}</span>
                          <span className="text-[10px] uppercase font-bold text-sakura-plum/60">{hc.status}</span>
                        </div>
                        <div className="text-[10px] text-sakura-plum/70 space-y-0.5">
                          {contestPrizes(hc).map((prize, index) => (
                            <div key={index}>{placeBadge(index)} {prize}</div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ================= STATS TAB ================= */}
      {activeAdminSubTab === 'stats' && (
        <div className="flex flex-col gap-3">
          {stats ? (
            <>
              {/* Counters Grid */}
              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-3.5 rounded-2xl bg-white/90 dark:bg-sakura-darkcard/90 border border-sakura-pink/30 shadow-xs">
                  <div className="flex items-center gap-2 text-sakura-rose">
                    <Users className="w-4 h-4" />
                    <span className="text-[11px] font-bold">Foydalanuvchilar</span>
                  </div>
                  <span className="text-xl font-black mt-1 block">{stats.total_users} ta</span>
                  <span className="text-[10px] text-sakura-plum/60">+ {stats.new_users_this_week} bu hafta</span>
                </div>

                <div className="p-3.5 rounded-2xl bg-white/90 dark:bg-sakura-darkcard/90 border border-sakura-pink/30 shadow-xs">
                  <div className="flex items-center gap-2 text-sakura-rose">
                    <ShoppingBag className="w-4 h-4" />
                    <span className="text-[11px] font-bold">Jami buyurtmalar</span>
                  </div>
                  <span className="text-xl font-black mt-1 block">{stats.total_orders} ta</span>
                  <span className="text-[10px] text-sakura-plum/60">{stats.new_orders} ta kutilmoqda</span>
                </div>
              </div>

              {/* Orders per day chart */}
              <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 border border-sakura-pink/30 shadow-sakura-sm">
                <h4 className="text-xs font-black text-sakura-plum dark:text-white mb-2 flex items-center gap-1.5">
                  <TrendingUp className="w-4 h-4 text-sakura-rose" />
                  <span>Oxirgi 7 kunlik buyurtmalar:</span>
                </h4>
                <div className="flex items-end justify-between h-24 pt-4 px-2">
                  {stats.orders_per_day.map((d, i) => {
                    const maxVal = Math.max(...stats.orders_per_day.map((x) => x.count), 1);
                    const heightPercent = Math.max((d.count / maxVal) * 100, 15);
                    return (
                      <div key={i} className="flex flex-col items-center flex-1">
                        <div
                          style={{ height: `${heightPercent}%` }}
                          className="w-4 rounded-t-md bg-gradient-to-t from-sakura-pink to-sakura-rose"
                        />
                        <span className="text-[9px] text-sakura-plum/60 mt-1">{d.date}</span>
                        <span className="text-[9px] font-bold text-sakura-rose">{d.count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Top Viewed Products */}
              <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 border border-sakura-pink/30 shadow-sakura-sm">
                <h4 className="text-xs font-black text-sakura-plum dark:text-white mb-2 flex items-center gap-1.5">
                  <Eye className="w-4 h-4 text-sakura-rose" />
                  <span>Eng ko'p ko'rilgan mahsulotlar:</span>
                </h4>
                <div className="space-y-1.5">
                  {stats.top_viewed_products.map((p, idx) => (
                    <div key={p.id} className="flex items-center justify-between text-xs py-1">
                      <span className="truncate pr-2">
                        {idx + 1}. {p.title}
                      </span>
                      <span className="font-bold text-sakura-rose shrink-0">{p.views} marta</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <p className="text-xs text-center py-4">Statistika yuklanmoqda...</p>
          )}
        </div>
      )}

      {/* ================= BROADCAST TAB ================= */}
      {activeAdminSubTab === 'broadcast' && (
        <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 border border-sakura-pink/30 shadow-sakura-sm">
          <h4 className="text-xs font-black text-sakura-plum dark:text-white mb-2 flex items-center gap-1.5">
            <Send className="w-4 h-4 text-sakura-rose" />
            <span>{t.broadcastMessage}</span>
          </h4>
          <p className="text-[11px] text-sakura-plum/70 dark:text-sakura-blush/70 mb-3">
            Xabar botdagi barcha mijozlarga xavfsiz (sekundiga ~25 ta tezlikda) yuboriladi.
          </p>

          <textarea
            rows={4}
            value={broadcastText}
            onChange={(e) => setBroadcastText(e.target.value)}
            placeholder="Xabar matni... 🌸 Masalan: Yangi jempirlar kolleksiyasi keldi!"
            className="w-full p-3 rounded-2xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 text-xs text-sakura-plum dark:text-white focus:outline-none focus:ring-1 focus:ring-sakura-rose resize-none mb-3"
          />

          {broadcastStatus && (
            <p className="text-xs font-bold text-emerald-600 mb-2">{broadcastStatus}</p>
          )}

          <button
            onClick={handleSendBroadcast}
            disabled={isBroadcasting || !broadcastText.trim()}
            className="w-full py-3 rounded-2xl bg-sakura-rose text-white font-black text-xs shadow-sakura active:scale-95 disabled:opacity-50"
          >
            {isBroadcasting ? "Tarqatilmoqda..." : "Yuborish 📣"}
          </button>
        </div>
      )}

      {/* ================= ADD/EDIT PRODUCT MODAL ================= */}
      {isProductModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-sm bg-white dark:bg-sakura-darkcard rounded-3xl p-5 shadow-sakura-lg border border-sakura-pink/40 animate-scale-in my-8 max-h-[90vh] overflow-y-auto">
            <h3 className="text-base font-black text-sakura-plum dark:text-white mb-3">
              {editingProduct ? 'Mahsulotni tahrirlash' : t.addNewProduct}
            </h3>

            <form onSubmit={handleSaveProduct} className="flex flex-col gap-2.5 text-xs">
              {/* Photo Upload from Phone Gallery */}
              <div>
                <label className="font-bold block mb-1">{t.uploadPhoto}</label>
                <div className="flex gap-2 items-center flex-wrap">
                  {photos.map((p, idx) => (
                    <div key={idx} className="relative w-14 h-14 rounded-xl overflow-hidden bg-sakura-blush">
                      <img src={getMediaUrl(p)} alt="" className="w-full h-full object-cover" />
                      <button
                        type="button"
                        onClick={() => setPhotos(photos.filter((_, i) => i !== idx))}
                        className="absolute top-0 right-0 bg-red-500 text-white text-[9px] w-4 h-4 flex items-center justify-center rounded-bl"
                      >
                        ✕
                      </button>
                    </div>
                  ))}

                  <label className="w-14 h-14 rounded-xl border-2 border-dashed border-sakura-rose/50 flex flex-col items-center justify-center text-sakura-rose cursor-pointer hover:bg-sakura-blush/30">
                    <Upload className="w-4 h-4" />
                    <span className="text-[8px] mt-0.5">{isUploadingPhoto ? '...' : '+ Foto'}</span>
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handlePhotoUpload}
                      disabled={isUploadingPhoto}
                    />
                  </label>
                </div>
              </div>

              <div>
                <label className="font-bold block mb-1">Nomi</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Masalan: Vintage Pushti Jempir 🌸"
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-bold block mb-1">Narxi (so'm)</label>
                  <input
                    type="text"
                    required
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="99000"
                    className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                  />
                </div>
                <div>
                  <label className="font-bold block mb-1">Eski narx (aksiya)</label>
                  <input
                    type="text"
                    value={oldPrice}
                    onChange={(e) => setOldPrice(e.target.value)}
                    placeholder="120000"
                    className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-bold block mb-1">Kategoriya</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 font-bold"
                  >
                    {categories.map((c) => (
                      <option key={c.slug} value={c.slug}>
                        #{c.slug} {c.emoji}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="font-bold block mb-1">Og'irligi (gramm)</label>
                  <input
                    type="text"
                    value={weightGrams}
                    onChange={(e) => setWeightGrams(e.target.value)}
                    placeholder="350"
                    className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold block mb-1">O'lchamlar (vergul bilan)</label>
                <input
                  type="text"
                  value={sizes}
                  onChange={(e) => setSizes(e.target.value)}
                  placeholder="S, M, L"
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Ranglar (vergul bilan)</label>
                <input
                  type="text"
                  value={colors}
                  onChange={(e) => setColors(e.target.value)}
                  placeholder="Pushti 🌸, Oq 🤍"
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">Tavsif</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Yumshoq, qulay va aesthetic..."
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 resize-none"
                />
              </div>

              <div className="flex gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setIsProductModalOpen(false)}
                  className="flex-1 py-2.5 rounded-xl border border-sakura-pink/30 font-bold"
                >
                  {t.cancel}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 py-2.5 rounded-xl bg-sakura-rose text-white font-black shadow-sakura"
                >
                  {isSubmitting ? 'Saqlanmoqda...' : t.save}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ================= CREATE CONTEST MODAL ================= */}
      {isContestModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-sm bg-white dark:bg-sakura-darkcard rounded-3xl p-5 shadow-sakura-lg border border-sakura-pink/40 animate-scale-in my-8 max-h-[90vh] overflow-y-auto">
            <h3 className="text-base font-black text-sakura-plum dark:text-white mb-1 flex items-center gap-2">
              <Gift className="w-5 h-5 text-sakura-rose" />
              <span>Yangi konkurs yaratish 🌸</span>
            </h3>
            <p className="text-[11px] text-sakura-plum/70 dark:text-sakura-blush/70 mb-4">
              Sovg'alarni va davomiylik muddatini belgilang.
            </p>

            <form onSubmit={handleCreateContest} className="flex flex-col gap-2.5 text-xs">
              <div>
                <label className="font-bold block mb-1 text-sakura-plum dark:text-white">
                  🥇 1-o'rin sovg'asi
                </label>
                <input
                  type="text"
                  required
                  value={cPrize1}
                  onChange={(e) => setCPrize1(e.target.value)}
                  placeholder="Masalan: 500.000 so'mlik vaucher yoki jempir 🌸"
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div>
                <label className="font-bold block mb-1 text-sakura-plum dark:text-white">
                  🥈 2-o'rin sovg'asi
                </label>
                <input
                  type="text"
                  required
                  value={cPrize2}
                  onChange={(e) => setCPrize2(e.target.value)}
                  placeholder="Masalan: 300.000 so'mlik vaucher 🎀"
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div>
                <label className="font-bold block mb-1 text-sakura-plum dark:text-white">
                  🥉 3-o'rin sovg'asi
                </label>
                <input
                  type="text"
                  required
                  value={cPrize3}
                  onChange={(e) => setCPrize3(e.target.value)}
                  placeholder="Masalan: Pushti scarf yoki sumka ✨"
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div>
                <label className="font-bold block mb-1 text-sakura-plum dark:text-white">
                  ⏳ Davomiyligi (kun)
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {[3, 5, 7, 14].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setCDurationDays(d)}
                      className={`py-2 rounded-xl text-xs font-bold transition-all ${
                        cDurationDays === d
                          ? 'bg-sakura-rose text-white shadow-xs'
                          : 'bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/30'
                      }`}
                    >
                      {d} kun
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2 p-2.5 rounded-xl bg-sakura-blush/30 dark:bg-sakura-darkcardsoft/40 border border-sakura-pink/20 mt-1">
                <input
                  type="checkbox"
                  id="onlyNewSubscribers"
                  checked={cOnlyNewSubscribers}
                  onChange={(e) => setCOnlyNewSubscribers(e.target.checked)}
                  className="accent-sakura-rose w-4 h-4 rounded"
                />
                <label htmlFor="onlyNewSubscribers" className="text-[11px] font-bold text-sakura-plum dark:text-white cursor-pointer">
                  Faqat yangi obunachilar hisoblansin (tavsiya etiladi) 🔒
                </label>
              </div>

              <div className="flex gap-2 mt-3">
                <button
                  type="button"
                  onClick={() => setIsContestModalOpen(false)}
                  className="flex-1 py-2.5 rounded-xl border border-sakura-pink/30 font-bold"
                >
                  {t.cancel}
                </button>
                <button
                  type="submit"
                  disabled={isCreatingContest}
                  className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white font-black shadow-sakura disabled:opacity-50"
                >
                  {isCreatingContest ? 'Yaratilmoqda...' : "Boshlash 🚀"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ================= EDIT PRIZES MODAL ================= */}
      {isEditPrizesModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-sm bg-white dark:bg-sakura-darkcard rounded-3xl p-5 shadow-sakura-lg border border-sakura-pink/40 animate-scale-in my-8">
            <h3 className="text-base font-black text-sakura-plum dark:text-white mb-2">
              Sovg'alarni o'zgartirish ✏️
            </h3>

            <form onSubmit={handleUpdatePrizes} className="flex flex-col gap-2.5 text-xs">
              <div>
                <label className="font-bold block mb-1">🥇 1-o'rin sovg'asi</label>
                <input
                  type="text"
                  required
                  value={editP1}
                  onChange={(e) => setEditP1(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">🥈 2-o'rin sovg'asi</label>
                <input
                  type="text"
                  required
                  value={editP2}
                  onChange={(e) => setEditP2(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div>
                <label className="font-bold block mb-1">🥉 3-o'rin sovg'asi</label>
                <input
                  type="text"
                  required
                  value={editP3}
                  onChange={(e) => setEditP3(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40"
                />
              </div>

              <div className="flex gap-2 mt-3">
                <button
                  type="button"
                  onClick={() => setIsEditPrizesModalOpen(false)}
                  className="flex-1 py-2.5 rounded-xl border border-sakura-pink/30 font-bold"
                >
                  {t.cancel}
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-sakura-rose text-white font-black shadow-sakura"
                >
                  {t.save}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
