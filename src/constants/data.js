import {
  Briefcase, MapPin, Umbrella, Coffee, Camera, Zap, Plus, Check, Home, Grid, Settings,
  ChevronLeft, AlertCircle, Sun, CloudRain, Backpack, Tent, GraduationCap, Heart, Music,
  Dumbbell, Trash2, Clock, Bell, Volume2, ChevronRight, Users, Share2, Smile, X, Lock,
  Mail, ArrowRight, Moon, User, UserPlus, Smartphone, Globe, Palette, Shield, HelpCircle, FileText
} from 'lucide-react';

export const THEMES = {
  cinnamon: {
    name: 'Cinnamon',
    bg: 'bg-[#FFFBF5]',
    cardBg: 'bg-white',
    textMain: 'text-[#5C5C5C]',
    textSub: 'text-[#9A9A9A]',
    primary: 'bg-[#E6B89C]',
    primaryText: 'text-[#C58968]',
    primaryBorder: 'border-[#E6B89C]',
    primaryHover: 'hover:bg-[#E6B89C]/90',
    primaryLight: 'bg-[#FAE8E0]',
    navActive: 'text-[#E6B89C]',
    accentBlue: 'bg-[#D0E6F0] text-[#6B8E9B]',
    accentGreen: 'bg-[#E0F0E3] text-[#7A9E83]',
    accentPink: 'bg-[#F4DCD6] text-[#C08585]',
    accentYellow: 'bg-[#F9EBC8] text-[#B59858]',
    accentPurple: 'bg-[#E8DEF2] text-[#9F8AB5]',
    danger: 'text-[#D98282] bg-[#FADCDC]',
    success: 'bg-[#CCD5AE]',
  },
  hazeBlue: {
    name: 'Haze Blue',
    bg: 'bg-[#F6F8FC]',
    cardBg: 'bg-white',
    textMain: 'text-[#334155]',
    textSub: 'text-[#64748B]',
    // Darker primary so white text stays readable (less "neon"/washed out)
    primary: 'bg-[#2B6CB0]',
    primaryText: 'text-[#2B6CB0]',
    primaryBorder: 'border-[#2B6CB0]',
    primaryHover: 'hover:bg-[#2B6CB0]/90',
    primaryLight: 'bg-[#E7F1FF]',
    navActive: 'text-[#2B6CB0]',
    accentBlue: 'bg-[#E8F2FF] text-[#1E4E8C]',
    accentGreen: 'bg-[#EAF7F1] text-[#1F6F57]',
    accentPink: 'bg-[#FBE9EE] text-[#9B3155]',
    accentYellow: 'bg-[#FFF4D6] text-[#8A6A18]',
    accentPurple: 'bg-[#F1ECFF] text-[#5B49A8]',
    danger: 'text-[#E53E3E] bg-[#FED7D7]',
    success: 'bg-[#16A34A]',
  },
  sageGreen: {
    name: 'Sage Green',
    bg: 'bg-[#F7FBF8]',
    cardBg: 'bg-white',
    // Use neutral body text; keep green as accent to reduce eye strain
    textMain: 'text-[#334155]',
    textSub: 'text-[#64748B]',
    primary: 'bg-[#2F855A]',
    primaryText: 'text-[#2F855A]',
    primaryBorder: 'border-[#2F855A]',
    primaryHover: 'hover:bg-[#2F855A]/90',
    primaryLight: 'bg-[#EAF7EF]',
    navActive: 'text-[#2F855A]',
    accentBlue: 'bg-[#E8F2FF] text-[#1E4E8C]',
    accentGreen: 'bg-[#EAF7EF] text-[#1F6F57]',
    accentPink: 'bg-[#FBE9EE] text-[#9B3155]',
    accentYellow: 'bg-[#FFF4D6] text-[#8A6A18]',
    accentPurple: 'bg-[#F1ECFF] text-[#5B49A8]',
    danger: 'text-[#E53E3E] bg-[#FED7D7]',
    success: 'bg-[#16A34A]',
  },
};

/** Dark UI variants (same keys as THEMES). */
export const THEMES_DARK = {
  cinnamon: {
    name: 'Cinnamon',
    bg: 'bg-[#161311]',
    cardBg: 'bg-[#221F1C]',
    textMain: 'text-[#EDE8E2]',
    textSub: 'text-[#9A928A]',
    primary: 'bg-[#B8896E]',
    primaryText: 'text-[#E8C9B0]',
    primaryBorder: 'border-[#B8896E]',
    primaryHover: 'hover:bg-[#B8896E]/90',
    primaryLight: 'bg-[#2A2420]',
    navActive: 'text-[#E8C9B0]',
    accentBlue: 'bg-[#2C3A42] text-[#9BB8C4]',
    accentGreen: 'bg-[#243028] text-[#8FB89A]',
    accentPink: 'bg-[#3A2826] text-[#D4A09A]',
    accentYellow: 'bg-[#353022] text-[#C9B87A]',
    accentPurple: 'bg-[#302A38] text-[#B5A8C8]',
    danger: 'text-[#F0A0A0] bg-[#3A2424]',
    success: 'bg-[#6B8F5E]',
  },
  hazeBlue: {
    name: 'Haze Blue',
    bg: 'bg-[#0B1220]',
    cardBg: 'bg-[#101A2B]',
    textMain: 'text-[#E2E8F0]',
    textSub: 'text-[#718096]',
    // Less neon, deeper primary
    primary: 'bg-[#1E3A8A]',
    primaryText: 'text-[#BFDBFE]',
    primaryBorder: 'border-[#1E3A8A]',
    primaryHover: 'hover:bg-[#1E3A8A]/90',
    primaryLight: 'bg-[#0F1E36]',
    navActive: 'text-[#BFDBFE]',
    accentBlue: 'bg-[#0F233D] text-[#9CC4FF]',
    accentGreen: 'bg-[#0F2B22] text-[#A7F3D0]',
    accentPink: 'bg-[#3A2826] text-[#D4A09A]',
    accentYellow: 'bg-[#353022] text-[#C9B87A]',
    accentPurple: 'bg-[#302A38] text-[#B5A8C8]',
    danger: 'text-[#FC8181] bg-[#3A2020]',
    success: 'bg-[#16A34A]',
  },
  sageGreen: {
    name: 'Sage Green',
    bg: 'bg-[#07140E]',
    cardBg: 'bg-[#0C1D15]',
    textMain: 'text-[#E2E8F0]',
    textSub: 'text-[#94A3B8]',
    primary: 'bg-[#166534]',
    primaryText: 'text-[#BBF7D0]',
    primaryBorder: 'border-[#166534]',
    primaryHover: 'hover:bg-[#166534]/90',
    primaryLight: 'bg-[#0E2A1D]',
    navActive: 'text-[#BBF7D0]',
    accentBlue: 'bg-[#0F233D] text-[#9CC4FF]',
    accentGreen: 'bg-[#0E2A1D] text-[#A7F3D0]',
    accentPink: 'bg-[#3A2826] text-[#D4A09A]',
    accentYellow: 'bg-[#353022] text-[#C9B87A]',
    accentPurple: 'bg-[#302A38] text-[#B5A8C8]',
    danger: 'text-[#FC8181] bg-[#3A2020]',
    success: 'bg-[#16A34A]',
  },
};

export const DEFAULT_APP_PREFS = {
  notifications: true,
  sounds: true,
  auto_location: true,
  dark_mode: false,
  language: 'en',
};

/**
 * @param {string} themeKey
 * @param {boolean} darkMode
 */
export function buildDisplayTheme(themeKey, darkMode) {
  const k = THEMES[themeKey] ? themeKey : 'cinnamon';
  const base = darkMode ? THEMES_DARK[k] || THEMES_DARK.cinnamon : THEMES[k];
  const isDark = !!darkMode;
  return {
    ...base,
    isDark,
    navMuted: isDark
      ? 'text-slate-500 hover:text-slate-300'
      : 'text-[#C0C0C0] hover:text-[#9A9A9A]',
    shell: isDark
      ? 'bg-slate-900/90 backdrop-blur-xl border-t border-slate-600'
      : 'bg-white/90 backdrop-blur-xl border-t border-[#EAEAEA]',
    fabRing: isDark ? 'border-slate-800' : 'border-white',
    sessionMask: isDark ? 'bg-slate-950/90 backdrop-blur-sm' : 'bg-white/85 backdrop-blur-sm',
    sessionSpinner: isDark ? 'border-slate-600 border-t-slate-200' : 'border-gray-200 border-t-gray-800',
  };
}

export const CURRENT_USER = { id: 'me', name: 'Me', avatar: 'https://api.dicebear.com/7.x/notionists/svg?seed=Felix' };

export const INITIAL_SCENARIOS = [
  {
    id: 'school',
    name: 'Go to School',
    icon: 'GraduationCap',
    theme: { bg: 'bg-[#D0E6F0]', text: 'text-[#6B8E9B]' },
    type: 'preset',
    collaborators: [],
    items: [
      { id: 's1', text: 'Student ID', critical: true, assignedTo: 'me' },
      { id: 's2', text: 'Homework/Essay', critical: true, assignedTo: 'me' },
      { id: 's3', text: 'Laptop', critical: false, assignedTo: 'me' },
      { id: 's4', text: 'Charger', critical: false, assignedTo: 'me' },
      { id: 's5', text: 'Water Bottle', critical: false, assignedTo: 'me' },
    ]
  },
  {
    id: 'work',
    name: 'Go to Work',
    icon: 'Briefcase',
    theme: { bg: 'bg-[#E5E5E5]', text: 'text-[#7D7D7D]' },
    type: 'preset',
    collaborators: [],
    items: [
      { id: 'w1', text: 'ID Badge', critical: true, assignedTo: 'me' },
      { id: 'w2', text: 'Smartphone', critical: true, assignedTo: 'me' },
      { id: 'w3', text: 'Laptop & Charger', critical: true, assignedTo: 'me' },
      { id: 'w4', text: 'Earbuds', critical: false, assignedTo: 'me' },
    ]
  },
  {
    id: 'gym',
    name: 'Go to Gym',
    icon: 'Dumbbell',
    theme: { bg: 'bg-[#F4DCD6]', text: 'text-[#C08585]' },
    type: 'preset',
    collaborators: [],
    items: [
      { id: 'g1', text: 'Gym Card', critical: true, assignedTo: 'me' },
      { id: 'g2', text: 'Change of Clothes', critical: false, assignedTo: 'me' },
      { id: 'g3', text: 'Towel', critical: false, assignedTo: 'me' },
      { id: 'g4', text: 'Water Bottle', critical: false, assignedTo: 'me' },
    ]
  },
  {
    id: 'camping',
    name: 'Weekend Camping',
    icon: 'Tent',
    theme: { bg: 'bg-[#F9EBC8]', text: 'text-[#B59858]' },
    type: 'preset',
    collaborators: [],
    items: [
      { id: 'c1', text: 'Tent', critical: true, assignedTo: 'me' },
      { id: 'c2', text: 'Sleeping Bag', critical: true, assignedTo: 'me' },
      { id: 'c3', text: 'Food & Ingredients', critical: true, assignedTo: 'me' },
    ]
  },
  {
    id: 'travel',
    name: 'Short Trip',
    icon: 'MapPin',
    theme: { bg: 'bg-[#E0F0E3]', text: 'text-[#7A9E83]' },
    type: 'preset',
    collaborators: [],
    items: [
      { id: 't1', text: 'ID Card / Passport', critical: true, assignedTo: 'me' },
      { id: 't2', text: 'Tickets', critical: true, assignedTo: 'me' },
      { id: 't3', text: 'Toiletry Bag', critical: false, assignedTo: 'me' },
    ]
  }
];

export const MOCK_HISTORY = [
  { id: 1, name: 'Go to Work', date: 'Today 08:30', status: 'completed' },
  { id: 2, name: 'Go to Gym', date: 'Yesterday 18:45', status: 'completed' },
];

export const IconMap = {
  GraduationCap, Briefcase, Dumbbell, MapPin, Heart,
  Camera, Tent, Music, Backpack, Coffee, Zap
};

/** Used when the weather API is offline or still loading. */
export const WEATHER_FALLBACK = {
  temp: null,
  condition: 'Unavailable',
  location: '—',
  comfort: '—',
  packingHint: 'Connect to the internet and refresh to load live weather.',
  iconKey: 'cloud',
  isDay: true,
  source: 'system-fallback',
};

/** @deprecated use WEATHER_FALLBACK */
export const WEATHER_DATA = WEATHER_FALLBACK;
