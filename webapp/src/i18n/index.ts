export type Language = 'uz' | 'en' | 'ru';

export interface Translations {
  shopName: string;
  tagline: string;
  searchPlaceholder: string;
  allCategories: string;
  newArrivals: string;
  hitProducts: string;
  productOfTheDay: string;
  soldOut: string;
  inStock: string;
  price: string;
  oldPrice: string;
  estimatedCargo: string;
  deliveryTerms: string;
  orderNotice: string;
  addToBag: string;
  addedToBag: string;
  orderNow: string;
  wishlist: string;
  bag: string;
  home: string;
  reviews: string;
  settings: string;
  adminPanel: string;
  sizes: string;
  colors: string;
  selectSize: string;
  selectColor: string;
  cargoRateTitle: string;
  deliveryTimeTitle: string;
  deliveryScopeTitle: string;
  prepaymentTitle: string;
  locationTitle: string;
  emptyBag: string;
  emptyBagSubtitle: string;
  emptyWishlist: string;
  emptyWishlistSubtitle: string;
  emptyReviews: string;
  subtotal: string;
  grandTotal: string;
  checkoutButton: string;
  orderSuccessTitle: string;
  orderSuccessSubtitle: string;
  orderCopyHint: string;
  copySummary: string;
  copied: string;
  messageAdminButton: string;
  continueShopping: string;
  languageSelect: string;
  fallingPetals: string;
  reducedMotion: string;
  on: string;
  off: string;
  leaveReview: string;
  submitReview: string;
  yourName: string;
  yourReview: string;
  reviewPendingNotice: string;
  adminDashboard: string;
  totalUsers: string;
  totalOrders: string;
  newOrders: string;
  productsCount: string;
  quickStockToggle: string;
  addNewProduct: string;
  uploadPhoto: string;
  postToChannel: string;
  broadcastMessage: string;
  save: string;
  cancel: string;
  delete: string;
  confirmDelete: string;
  orderStatusNew: string;
  orderStatusAccepted: string;
  orderStatusCancelled: string;
  contest: string;
  contestTitle: string;
  contestPrizes: string;
  firstPrize: string;
  secondPrize: string;
  thirdPrize: string;
  timeRemaining: string;
  myLink: string;
  copyLink: string;
  shareLink: string;
  myScore: string;
  myRank: string;
  leaderboard: string;
  myInvites: string;
  noActiveContest: string;
  statusConfirmed: string;
  statusPending: string;
  statusRevoked: string;
  newContestBtn: string;
}

export const translations: Record<Language, Translations> = {
  uz: {
    shopName: 'Sakura shop',
    tagline: 'Xitoy brendlari & Aesthetic kiyimlar 🌸',
    searchPlaceholder: 'Mahsulotlarni qidirish... 🎀',
    allCategories: 'Barchasi',
    newArrivals: '🆕 Yangi kelganlar',
    hitProducts: '🔥 Eng ommabop (Hit)',
    productOfTheDay: 'Kun mahsuloti 🌸',
    soldOut: 'Sotildi',
    inStock: 'Sotuvda mavjud',
    price: 'Narxi',
    oldPrice: 'Eski narxi',
    estimatedCargo: 'Taxminiy kargo',
    deliveryTerms: "Yetkazib berish shartlari 📦",
    orderNotice: "Buyurtma berish uchun @fkhrdnvvvva ga yozing 💌",
    addToBag: "Savatga qo'shish 🛍️",
    addedToBag: "Savatga qo'shildi! 🌸",
    orderNow: "Hoziroq so'rash 💌",
    wishlist: "Istaklar",
    bag: "Savat",
    home: "Asosiy",
    reviews: "Fikrlar",
    settings: "Sozlamalar",
    adminPanel: "Admin",
    sizes: "O'lchamlar",
    colors: "Ranglar",
    selectSize: "O'lchamni tanlang:",
    selectColor: "Rangni tanlang:",
    cargoRateTitle: "Kargo",
    deliveryTimeTitle: "Yetkazib berish",
    deliveryScopeTitle: "Dastavka",
    prepaymentTitle: "To'lov",
    locationTitle: "Joylashuv",
    emptyBag: "Savatingiz bo'sh 🌸",
    emptyBagSubtitle: "Yoqqan kiyimlarni savatga qo'shing va buyurtma bering!",
    emptyWishlist: "Istaklar ro'yxati bo'sh 💗",
    emptyWishlistSubtitle: "O'zingizga yoqqan mahsulotlarga yurakcha bosing!",
    emptyReviews: "Hozircha fikrlar yo'q ⭐️",
    subtotal: "Mahsulotlar narxi",
    grandTotal: "Jami to'lov",
    checkoutButton: "Buyurtma berish 💌",
    orderSuccessTitle: "Rahmat! Buyurtmangiz qabul qilindi 🌸",
    orderSuccessSubtitle: "Admin tez orada siz bilan bog'lanadi. Tezroq javob olish uchun quyidagi matnni nusxalab egamizga yuborishingiz mumkin!",
    orderCopyHint: "Nusxalash uchun bosing:",
    copySummary: "Matnni nusxalash 📋",
    copied: "Nusxalandi! ✅",
    messageAdminButton: "@fkhrdnvvvva ga yozish 💌",
    continueShopping: "Xaridni davom ettirish 🛍️",
    languageSelect: "Tilni tanlang / Language",
    fallingPetals: "Sakura barglari yog'ishi 🌸",
    reducedMotion: "Harakatlarni kamaytirish",
    on: "Yoqilgan",
    off: "O'chirilgan",
    leaveReview: "Fikr bildirish ✍️",
    submitReview: "Yuborish",
    yourName: "Ismingiz",
    yourReview: "Fikringizni yozing...",
    reviewPendingNotice: "Fikringiz admin tasdiqlaganidan so'ng ko'rinadi 🌸",
    adminDashboard: "Admin boshqaruvi 👑",
    totalUsers: "Foydalanuvchilar",
    totalOrders: "Buyurtmalar",
    newOrders: "Yangi buyurtmalar",
    productsCount: "Mahsulotlar",
    quickStockToggle: "Tezkor sotuv holati",
    addNewProduct: "Yangi mahsulot qo'shish ➕",
    uploadPhoto: "Galereyadan rasm yuklash 📸",
    postToChannel: "Kanalga joylash 📢",
    broadcastMessage: "Hamma foydalanuvchilarga xabar 📣",
    save: "Saqlash",
    cancel: "Bekor qilish",
    delete: "O'chirish",
    confirmDelete: "Rostdan ham o'chirmoqchimisiz?",
    orderStatusNew: "Yangi",
    orderStatusAccepted: "Qabul qilingan",
    orderStatusCancelled: "Bekor qilingan",
    contest: "Konkurs",
    contestTitle: "Sakura Referral Konkurs 🌸",
    contestPrizes: "Sovg'alar",
    firstPrize: "1-o'rin sovg'asi",
    secondPrize: "2-o'rin sovg'asi",
    thirdPrize: "3-o'rin sovg'asi",
    timeRemaining: "Tugash vaqti",
    myLink: "Mening taklif havolam",
    copyLink: "Nusxa olish 📋",
    shareLink: "Do'stlarga ulashish 📤",
    myScore: "Ballingiz",
    myRank: "O'rningiz",
    leaderboard: "Yetakchilar jadvali 🏆",
    myInvites: "Mening takliflarim 👥",
    noActiveContest: "Hozircha faol konkurs yo'q 🌸",
    statusConfirmed: "Tasdiqlangan",
    statusPending: "Kutilmoqda",
    statusRevoked: "Chiqib ketgan",
    newContestBtn: "Yangi konkurs 🎁",
  },
  en: {
    shopName: 'Sakura shop',
    tagline: 'Chinese brand & aesthetic apparel 🌸',
    searchPlaceholder: 'Search products... 🎀',
    allCategories: 'All',
    newArrivals: '🆕 New Arrivals',
    hitProducts: '🔥 Hit Products',
    productOfTheDay: 'Product of the Day 🌸',
    soldOut: 'Sold Out',
    inStock: 'In Stock',
    price: 'Price',
    oldPrice: 'Old Price',
    estimatedCargo: 'Estimated Cargo',
    deliveryTerms: 'Delivery Terms 📦',
    orderNotice: 'To order, message @fkhrdnvvvva 💌',
    addToBag: 'Add to Bag 🛍️',
    addedToBag: 'Added to Bag! 🌸',
    orderNow: 'Ask Now 💌',
    wishlist: 'Wishlist',
    bag: 'Bag',
    home: 'Home',
    reviews: 'Reviews',
    settings: 'Settings',
    adminPanel: 'Admin',
    sizes: 'Sizes',
    colors: 'Colors',
    selectSize: 'Select size:',
    selectColor: 'Select color:',
    cargoRateTitle: 'Cargo',
    deliveryTimeTitle: 'Delivery Time',
    deliveryScopeTitle: 'Shipping Area',
    prepaymentTitle: 'Payment',
    locationTitle: 'Location',
    emptyBag: 'Your bag is empty 🌸',
    emptyBagSubtitle: 'Browse aesthetic items and add them to your bag!',
    emptyWishlist: 'Your wishlist is empty 💗',
    emptyWishlistSubtitle: 'Tap the heart icon on items you love!',
    emptyReviews: 'No reviews yet ⭐️',
    subtotal: 'Items Subtotal',
    grandTotal: 'Total Estimate',
    checkoutButton: 'Place Order 💌',
    orderSuccessTitle: 'Thank you! Order placed 🌸',
    orderSuccessSubtitle: 'The admin will contact you shortly. You can also copy your order summary and send it directly to her!',
    orderCopyHint: 'Tap to copy:',
    copySummary: 'Copy Summary 📋',
    copied: 'Copied! ✅',
    messageAdminButton: 'Message @fkhrdnvvvva 💌',
    continueShopping: 'Continue Shopping 🛍️',
    languageSelect: 'Choose Language',
    fallingPetals: 'Falling Sakura Petals 🌸',
    reducedMotion: 'Reduced Motion',
    on: 'On',
    off: 'Off',
    leaveReview: 'Leave a Review ✍️',
    submitReview: 'Submit',
    yourName: 'Your Name',
    yourReview: 'Write your thoughts...',
    reviewPendingNotice: 'Your review will be visible after admin approval 🌸',
    adminDashboard: 'Admin Dashboard 👑',
    totalUsers: 'Total Users',
    totalOrders: 'Total Orders',
    newOrders: 'New Orders',
    productsCount: 'Products',
    quickStockToggle: 'Quick Stock Toggle',
    addNewProduct: 'Add New Product ➕',
    uploadPhoto: 'Upload Photo 📸',
    postToChannel: 'Post to Channel 📢',
    broadcastMessage: 'Broadcast Message 📣',
    save: 'Save',
    cancel: 'Cancel',
    delete: 'Delete',
    confirmDelete: 'Are you sure you want to delete this?',
    orderStatusNew: 'New',
    orderStatusAccepted: 'Accepted',
    orderStatusCancelled: 'Cancelled',
    contest: 'Contest',
    contestTitle: 'Sakura Referral Contest 🌸',
    contestPrizes: 'Prizes',
    firstPrize: '1st Place Prize',
    secondPrize: '2nd Place Prize',
    thirdPrize: '3rd Place Prize',
    timeRemaining: 'Ends At',
    myLink: 'My Referral Link',
    copyLink: 'Copy Link 📋',
    shareLink: 'Share with Friends 📤',
    myScore: 'Your Score',
    myRank: 'Your Rank',
    leaderboard: 'Leaderboard 🏆',
    myInvites: 'My Invites 👥',
    noActiveContest: 'No active contest right now 🌸',
    statusConfirmed: 'Confirmed',
    statusPending: 'Pending',
    statusRevoked: 'Left Channel',
    newContestBtn: 'New Contest 🎁',
  },
  ru: {
    shopName: 'Sakura shop',
    tagline: 'Китайские бренды и aesthetic одежда 🌸',
    searchPlaceholder: 'Поиск товаров... 🎀',
    allCategories: 'Все',
    newArrivals: '🆕 Новинки',
    hitProducts: '🔥 Хиты продаж',
    productOfTheDay: 'Товар дня 🌸',
    soldOut: 'Продано',
    inStock: 'В наличии',
    price: 'Цена',
    oldPrice: 'Старая цена',
    estimatedCargo: 'Примерное карго',
    deliveryTerms: 'Условия доставки 📦',
    orderNotice: 'Для заказа напишите @fkhrdnvvvva 💌',
    addToBag: 'В корзину 🛍️',
    addedToBag: 'Добавлено в корзину! 🌸',
    orderNow: 'Спросить сейчас 💌',
    wishlist: 'Избранное',
    bag: 'Корзина',
    home: 'Главная',
    reviews: 'Отзывы',
    settings: 'Настройки',
    adminPanel: 'Админ',
    sizes: 'Размеры',
    colors: 'Цвета',
    selectSize: 'Выберите размер:',
    selectColor: 'Выберите цвет:',
    cargoRateTitle: 'Карго',
    deliveryTimeTitle: 'Сроки доставки',
    deliveryScopeTitle: 'Доставка',
    prepaymentTitle: 'Оплата',
    locationTitle: 'Локация',
    emptyBag: 'Ваша корзина пуста 🌸',
    emptyBagSubtitle: 'Добавьте понравившиеся вещи в корзину и оформите заказ!',
    emptyWishlist: 'Список желаний пуст 💗',
    emptyWishlistSubtitle: 'Нажмите на сердечко, чтобы сохранить любимые вещи!',
    emptyReviews: 'Пока нет отзывов ⭐️',
    subtotal: 'Сумма товаров',
    grandTotal: 'Итого',
    checkoutButton: 'Оформить заказ 💌',
    orderSuccessTitle: 'Спасибо! Заказ оформлен 🌸',
    orderSuccessSubtitle: 'Администратор скоро свяжется с вами. Для быстрого оформления скопируйте текст и отправьте владелице!',
    orderCopyHint: 'Нажмите для копирования:',
    copySummary: 'Скопировать детали 📋',
    copied: 'Скопировано! ✅',
    messageAdminButton: 'Написать @fkhrdnvvvva 💌',
    continueShopping: 'Продолжить покупки 🛍️',
    languageSelect: 'Выберите язык',
    fallingPetals: 'Падающие лепестки сакуры 🌸',
    reducedMotion: 'Уменьшение движения',
    on: 'Вкл',
    off: 'Выкл',
    leaveReview: 'Оставить отзыв ✍️',
    submitReview: 'Отправить',
    yourName: 'Ваше имя',
    yourReview: 'Напишите ваш отзыв...',
    reviewPendingNotice: 'Отзыв появится после проверки администратором 🌸',
    adminDashboard: 'Панель администратора 👑',
    totalUsers: 'Пользователи',
    totalOrders: 'Все заказы',
    newOrders: 'Новые заказы',
    productsCount: 'Товары',
    quickStockToggle: 'Быстрое переключение наличия',
    addNewProduct: 'Добавить товар ➕',
    uploadPhoto: 'Загрузить фото 📸',
    postToChannel: 'Опубликовать в канал 📢',
    broadcastMessage: 'Рассылка всем пользователям 📣',
    save: 'Сохранить',
    cancel: 'Отмена',
    delete: 'Удалить',
    confirmDelete: 'Вы уверены, что хотите удалить?',
    orderStatusNew: 'Новый',
    orderStatusAccepted: 'Принят',
    orderStatusCancelled: 'Отменен',
    contest: 'Конкурс',
    contestTitle: 'Реферальный Конкурс Сакура 🌸',
    contestPrizes: 'Призы',
    firstPrize: 'Приз за 1-е место',
    secondPrize: 'Приз за 2-е место',
    thirdPrize: 'Приз за 3-е место',
    timeRemaining: 'Завершение',
    myLink: 'Моя реферальная ссылка',
    copyLink: 'Копировать ссылку 📋',
    shareLink: 'Поделиться с друзьями 📤',
    myScore: 'Ваши баллы',
    myRank: 'Ваше место',
    leaderboard: 'Таблица лидеров 🏆',
    myInvites: 'Мои приглашения 👥',
    noActiveContest: 'Сейчас нет активного конкурса 🌸',
    statusConfirmed: 'Подтвержден',
    statusPending: 'Ожидает',
    statusRevoked: 'Вышел из канала',
    newContestBtn: 'Новый конкурс 🎁',
  },
};
