export interface Product {
  id: number;
  title: string;
  description: string;
  price: number;
  old_price?: number | null;
  category: string;
  photos: string[];
  sizes: string[];
  colors: string[];
  weight_grams?: number | null;
  in_stock: boolean;
  is_new: boolean;
  is_hit: boolean;
  views: number;
  created_at: string;
  formatted_price: string;
  formatted_old_price?: string | null;
  cargo_estimate: number;
  formatted_cargo_estimate: string;
}

export interface Category {
  slug: string;
  name: string;
  emoji: string;
  sort_order: number;
  product_count: number;
}

export interface CartItem {
  id: number;
  product_id: number;
  product_title: string;
  product_price: number;
  product_photo?: string | null;
  size?: string | null;
  color?: string | null;
  qty: number;
  weight_grams?: number | null;
  item_total: number;
  formatted_item_total: string;
}

export interface CartSummary {
  items: CartItem[];
  total_items: number;
  subtotal: number;
  formatted_subtotal: string;
  estimated_cargo: number;
  formatted_estimated_cargo: string;
  grand_total: number;
  formatted_grand_total: string;
}

export interface Order {
  id: number;
  user_id: number;
  customer_name: string;
  customer_username?: string | null;
  items_snapshot: any[];
  total: number;
  formatted_total: string;
  estimated_cargo: number;
  formatted_cargo: string;
  status: 'new' | 'accepted' | 'cancelled';
  created_at: string;
}

export interface Review {
  id: number;
  photos: string[];
  text: string;
  customer_name: string;
  approved: boolean;
  created_at: string;
}

export interface ShopSettings {
  cargo_rate: number;
  delivery_days: string;
  delivery_scope: string;
  payment_terms: string;
  location: string;
  contact_username: string;
  channel_url: string;
  has_linked_channel: boolean;
  welcome_text: string;
}

export interface AdminStats {
  total_users: number;
  new_users_this_week: number;
  total_orders: number;
  new_orders: number;
  accepted_orders: number;
  total_products: number;
  in_stock_products: number;
  top_viewed_products: Product[];
  most_wishlisted_products: {
    product_id: number;
    title: string;
    wishlist_count: number;
    price: number;
    formatted_price: string;
    photo: string;
  }[];
  orders_per_day: {
    date: string;
    count: number;
  }[];
}

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_admin?: boolean;
  is_owner?: boolean;
}

export interface Contest {
  id: number;
  prize_1: string;
  prize_2: string;
  prize_3: string;
  photo_file_id?: string | null;
  channel_message_id?: number | null;
  status: string;
  only_new_subscribers: boolean;
  created_at: string;
  ends_at: string;
  formatted_ends_at: string;
  is_active: boolean;
  total_participants?: number;
  total_confirmed_invites?: number;
  channel_url: string;
  winners_snapshot?: any[];
  total_subscribers_gained?: number;
}

export interface LeaderboardEntry {
  rank: number;
  user_id: number;
  name: string;
  username?: string | null;
  score: number;
  last_confirmed_at?: string | null;
}

export interface ContestInviteItem {
  id: number;
  invitee_id: number;
  name: string;
  username?: string | null;
  status: 'pending' | 'confirmed' | 'revoked';
  started_at: string;
  confirmed_at?: string | null;
}

export interface MyContestStats {
  has_active_contest: boolean;
  contest?: Contest | null;
  user_id: number;
  invite_link: string;
  score: number;
  rank?: number | null;
  next_rank_score?: number | null;
  invites: ContestInviteItem[];
}

export interface SuspiciousUserItem {
  referrer_id: number;
  name: string;
  username?: string | null;
  total_invites: number;
  confirmed_invites: number;
  revoked_invites: number;
  revoked_ratio: number;
}
