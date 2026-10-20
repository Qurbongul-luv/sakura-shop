import React, { useState } from 'react';
import { Star, MessageSquarePlus, Check, Image as ImageIcon } from 'lucide-react';
import { Review } from '../types';
import { getMediaUrl } from '../utils/format';
import { haptic } from '../utils/telegram';
import { EmptyState } from '../components/EmptyState';
import { Translations } from '../i18n';

interface ReviewsPageProps {
  reviews: Review[];
  onReviewSubmitted: (review: Review) => void;
  t: Translations;
  initData: string;
}

export const ReviewsPage: React.FC<ReviewsPageProps> = ({
  reviews,
  onReviewSubmitted,
  t,
  initData,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [text, setText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedMessage, setSubmittedMessage] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customerName.trim()) return;

    setIsSubmitting(true);
    haptic.impact('medium');

    try {
      const resp = await fetch('/api/reviews', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({
          customer_name: customerName.trim(),
          text: text.trim(),
          photos: [],
        }),
      });

      if (resp.ok) {
        const newRev: Review = await resp.json();
        onReviewSubmitted(newRev);
        setSubmittedMessage(true);
        setTimeout(() => {
          setSubmittedMessage(false);
          setIsModalOpen(false);
          setText('');
        }, 2000);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="pb-32 px-4 max-w-md mx-auto">
      {/* Header & Write Review Button */}
      <div className="py-3 flex items-center justify-between">
        <h2 className="text-lg font-black text-sakura-plum dark:text-white flex items-center gap-2">
          <span>⭐</span>
          <span>{t.reviews} (#отзыв)</span>
        </h2>

        <button
          onClick={() => {
            haptic.selection();
            setIsModalOpen(true);
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-gradient-to-r from-sakura-pink to-sakura-rose text-white font-bold text-xs shadow-sakura active:scale-95 transition-transform"
        >
          <MessageSquarePlus className="w-3.5 h-3.5" />
          <span>{t.leaveReview}</span>
        </button>
      </div>

      {/* Reviews List */}
      {reviews.length === 0 ? (
        <EmptyState
          title={t.emptyReviews}
          subtitle="Do'konimizdan birinchi bo'lib xarid qiling va o'z fikringizni qoldiring! 🌸"
        />
      ) : (
        <div className="flex flex-col gap-3">
          {reviews.map((r) => (
            <div
              key={r.id}
              className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-extrabold text-sm text-sakura-plum dark:text-white">
                  {r.customer_name}
                </span>
                <div className="flex items-center text-amber-400">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <Star key={i} className="w-3.5 h-3.5 fill-amber-400" />
                  ))}
                </div>
              </div>

              {r.text && (
                <p className="text-xs sm:text-sm text-sakura-plum/80 dark:text-sakura-blush/80 leading-relaxed whitespace-pre-line">
                  "{r.text}"
                </p>
              )}

              {/* Review Photos if any */}
              {r.photos && r.photos.length > 0 && (
                <div className="mt-3 flex gap-2 overflow-x-auto">
                  {r.photos.map((p, idx) => (
                    <img
                      key={idx}
                      src={getMediaUrl(p)}
                      alt=""
                      className="w-16 h-16 rounded-xl object-cover bg-sakura-blush/50"
                    />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Leave Review Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-white dark:bg-sakura-darkcard rounded-3xl p-5 shadow-sakura-lg border border-sakura-pink/40 animate-scale-in">
            <h3 className="text-base font-black text-sakura-plum dark:text-white mb-3">
              {t.leaveReview}
            </h3>

            {submittedMessage ? (
              <div className="p-4 rounded-2xl bg-sakura-blush text-center">
                <span className="text-2xl">🌸</span>
                <p className="text-xs font-bold text-sakura-rose mt-1">
                  {t.reviewPendingNotice}
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <div>
                  <label className="text-[11px] font-bold text-sakura-plum/80 block mb-1">
                    {t.yourName}
                  </label>
                  <input
                    type="text"
                    required
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Masalan: Nilufar 🌸"
                    className="w-full px-3 py-2 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 text-xs text-sakura-plum dark:text-white focus:outline-none focus:ring-1 focus:ring-sakura-rose"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-bold text-sakura-plum/80 block mb-1">
                    {t.yourReview}
                  </label>
                  <textarea
                    rows={3}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Mahsulot sifati, rangi va yetkazib berish haqida..."
                    className="w-full px-3 py-2 rounded-xl bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 text-xs text-sakura-plum dark:text-white focus:outline-none focus:ring-1 focus:ring-sakura-rose resize-none"
                  />
                </div>

                <div className="flex gap-2 mt-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="flex-1 py-2.5 rounded-xl border border-sakura-pink/30 text-xs font-bold text-sakura-plum/70 hover:bg-sakura-blush/40"
                  >
                    {t.cancel}
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="flex-1 py-2.5 rounded-xl bg-sakura-rose text-white text-xs font-black shadow-sakura hover:opacity-95"
                  >
                    {isSubmitting ? 'Yuborilmoqda...' : t.submitReview}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
