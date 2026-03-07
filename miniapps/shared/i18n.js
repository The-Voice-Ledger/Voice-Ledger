/**
 * Voice Ledger Mini-App — i18n (English + Amharic)
 *
 * Usage:
 *   <script src="/miniapps/shared/i18n.js"></script>
 *   vlI18n.setLang('am');
 *   vlI18n.t('home');          // → 'መነሻ'
 *   vlI18n.translatePage();    // translates all [data-i18n] elements
 */

window.vlI18n = (() => {
  const strings = {
    en: {
      /* ── Tab bar ─────────────────────────── */
      home: 'Home',
      batches: 'Batches',
      assistant: 'Assistant',
      market: 'Market',
      profile: 'Profile',

      /* ── Index / home ────────────────────── */
      app_title: 'Voice Ledger',
      app_subtitle: 'Voice-First from Farm to Market',
      app_tagline: 'GS1 EPCIS 2.0 · Blockchain Traceability',
      menu_batches: 'My Batches',
      menu_batches_desc: 'View and manage coffee batches',
      menu_market: 'Marketplace',
      menu_market_desc: 'Browse and respond to RFQs',
      menu_trace: 'Trace',
      menu_trace_desc: 'Track batch journey on-chain',
      menu_assistant: 'Assistant',
      menu_assistant_desc: 'Ask anything about your supply chain',
      menu_profile: 'Profile',
      menu_profile_desc: 'Your account and credentials',
      menu_admin: 'Admin',
      menu_admin_desc: 'System administration',

      /* ── Assistant ───────────────────────── */
      assistant_title: 'Voice Ledger Assistant',
      assistant_subtitle: 'Ask anything about your coffee supply chain',
      assistant_empty_title: 'How can I help?',
      assistant_empty_desc: 'Ask about batches, RFQs, traceability, compliance, or anything else.',
      assistant_prompt_1: 'Show my batches',
      assistant_prompt_2: 'Available containers',
      assistant_prompt_3: 'EUDR compliance',
      assistant_prompt_4: 'Trace a batch',
      assistant_placeholder: 'Type a message...',
      assistant_voice_msg: 'Voice message',
      assistant_voice_fail: 'Voice processing failed. Try typing instead.',
      assistant_error: 'Sorry, something went wrong. Please try again.',
      new_chat: 'New chat',

      /* ── Batch browser ───────────────────── */
      batch_title: 'My Coffee Batches',
      batch_subtitle: 'Track and manage your production',
      batch_search: 'Search by batch ID, GTIN...',
      batch_all: 'All',
      batch_active: 'Active',
      batch_verified: 'Verified',
      batch_processed: 'Processed',
      batch_shipped: 'Shipped',
      batch_empty: 'No batches found',
      batch_empty_hint: 'Create your first batch using voice commands',
      batch_no_match: 'No batches match your filter',
      batch_details: 'Batch Details',
      batch_info: 'Batch Information',
      batch_quantity: 'Quantity',
      batch_variety: 'Variety',
      batch_origin: 'Origin',
      batch_processing: 'Processing',
      batch_grade: 'Grade',
      batch_status: 'Status',
      batch_created: 'Created',
      batch_verified_date: 'Verified',
      batch_timeline: 'Timeline',

      /* ── Marketplace ─────────────────────── */
      market_title: 'Marketplace',
      market_tab_rfqs: 'Open RFQs',
      market_tab_containers: 'My Containers',
      market_tab_offers: 'My Offers',
      market_search: 'Search RFQs...',
      market_all: 'All',
      market_open: 'Open',
      market_closed: 'Closed',
      market_arabica: 'Arabica',
      market_robusta: 'Robusta',
      market_empty: 'No RFQs found',
      market_no_containers: 'No containers listed yet',
      market_no_containers_hint: 'Your cooperative\'s container offerings will appear here',
      market_no_offers: 'No offers submitted yet',
      market_submit_offer: 'Submit Offer',
      market_quantity: 'Quantity (kg)',
      market_price: 'Price per kg (USD)',
      market_delivery: 'Delivery Timeline (days)',
      market_notes: 'Additional Notes',
      market_notes_placeholder: 'Optional notes...',
      market_submit: 'Submit Offer',
      market_success: 'Your offer has been submitted!',
      market_offer_failed: 'Failed to submit offer',
      market_price_required: 'Price is required',
      market_deadline: 'Deadline',
      market_view: 'View Details',
      market_buyer: 'Buyer',
      market_your_price: 'Your price',
      market_rfq_details: 'RFQ Details',
      market_coffee_type: 'Coffee Type',
      market_target_price: 'Target Price',
      market_status: 'Status',
      market_container_info: 'Container Info',
      market_grade: 'Grade',
      market_processing: 'Processing',
      market_total: 'Total',
      market_sold: 'Sold',
      market_available_qty: 'Available',
      market_listed: 'Listed',
      market_expires: 'Expires',
      market_fill_progress: 'Fill Progress',
      market_buyers: 'buyers',
      market_pools: 'pools',

      /* ── Trace ───────────────────────────── */
      trace_title: 'Trace Coffee',
      trace_search: 'Search batch ID or lot number...',
      trace_empty_title: 'No Batch Selected',
      trace_empty_desc: 'Select a batch to view trace information',
      trace_details: 'Batch Details',
      trace_journey: 'Journey Timeline',
      trace_location: 'Location Trail',
      trace_map_soon: 'Map visualization coming soon',
      trace_blockchain: 'Blockchain Verification',
      trace_tx_hash: 'Transaction Hash',
      trace_verified: 'Verified on Blockchain',
      trace_not_anchored: 'Not yet anchored',
      trace_loading: 'Loading trace data...',

      /* ── Profile ─────────────────────────── */
      profile_title: 'My Profile',
      profile_account: 'Account Information',
      profile_telegram_id: 'Telegram ID',
      profile_phone: 'Phone Number',
      profile_role: 'Role',
      profile_org: 'Organization',
      profile_language: 'Language',
      profile_not_set: 'Not set',
      profile_none: 'None',
      profile_approved: 'Approved',

      /* ── Admin ───────────────────────────── */
      admin_title: 'Admin Dashboard',
      admin_pending: 'Pending',
      admin_users: 'Users',
      admin_rfqs: 'RFQs',
      admin_offers: 'Offers',
      admin_tab_registrations: 'Registrations',
      admin_tab_users: 'Users',
      admin_tab_rfqs: 'RFQs',
      admin_tab_offers: 'Offers',
      admin_approve: 'Approve',
      admin_reject: 'Reject',
      admin_name: 'Name',
      admin_phone: 'Phone',
      admin_role: 'Role',
      admin_actions: 'Actions',
      admin_status: 'Status',
      admin_quantity: 'Quantity',
      admin_coffee_type: 'Coffee Type',
      admin_price: 'Price/kg',
      admin_cooperative: 'Cooperative',
      admin_no_pending: 'No pending registrations',

      /* ── Common ──────────────────────────── */
      loading: 'Loading...',
      error: 'Error',
      close: 'Close',
      back: 'Back',
      refresh: 'Refresh',
      english: 'EN',
      amharic: 'AM',
    },

    am: {
      /* ── Tab bar ─────────────────────────── */
      home: 'መነሻ',
      batches: 'ጥቅሎች',
      assistant: 'ረዳት',
      market: 'ገበያ',
      profile: 'መገለጫ',

      /* ── Index / home ────────────────────── */
      app_title: 'Voice Ledger',
      app_subtitle: 'ከእርሻ ወደ ገበያ በድምጽ',
      app_tagline: 'GS1 EPCIS 2.0 · ብሎክቼይን ምርመራ',
      menu_batches: 'ጥቅሎቼ',
      menu_batches_desc: 'የቡና ጥቅሎችን ይመልከቱ',
      menu_market: 'ገበያ',
      menu_market_desc: 'የRFQ ጥያቄዎችን ይመልከቱ',
      menu_trace: 'ክትትል',
      menu_trace_desc: 'የጥቅል ጉዞ ይከታተሉ',
      menu_assistant: 'ረዳት',
      menu_assistant_desc: 'ስለ አቅርቦት ሰንሰለትዎ ይጠይቁ',
      menu_profile: 'መገለጫ',
      menu_profile_desc: 'መለያዎ እና ምስክርነቶች',
      menu_admin: 'አስተዳዳሪ',
      menu_admin_desc: 'የስርዓት አስተዳደር',

      /* ── Assistant ───────────────────────── */
      assistant_title: 'Voice Ledger ረዳት',
      assistant_subtitle: 'ስለ ቡና አቅርቦት ሰንሰለትዎ ይጠይቁ',
      assistant_empty_title: 'እንዴት ልረዳዎ?',
      assistant_empty_desc: 'ስለ ጥቅሎች፣ RFQ፣ ክትትል፣ ተገዢነት ወይም ሌላ ማንኛውንም ነገር ይጠይቁ።',
      assistant_prompt_1: 'ጥቅሎቼን አሳይ',
      assistant_prompt_2: 'ያሉ ኮንቴይነሮች',
      assistant_prompt_3: 'EUDR ተገዢነት',
      assistant_prompt_4: 'ጥቅል ይከታተሉ',
      assistant_placeholder: 'መልእክት ይጻፉ...',
      assistant_voice_msg: 'የድምጽ መልእክት',
      assistant_voice_fail: 'ድምጽ ማቀናበር አልተሳካም። ከመጻፍ ይሞክሩ።',
      assistant_error: 'ይቅርታ፣ ስህተት ተፈጥሯል። እባክዎ እንደገና ይሞክሩ።',
      new_chat: 'አዲስ ውይይት',

      /* ── Batch browser ───────────────────── */
      batch_title: 'የቡና ጥቅሎቼ',
      batch_subtitle: 'ምርትዎን ይከታተሉ',
      batch_search: 'በጥቅል ID፣ GTIN ይፈልጉ...',
      batch_all: 'ሁሉም',
      batch_active: 'ንቁ',
      batch_verified: 'የተረጋገጠ',
      batch_processed: 'የተቀነባበረ',
      batch_shipped: 'የተላከ',
      batch_empty: 'ጥቅሎች አልተገኙም',
      batch_empty_hint: 'የመጀመሪያ ጥቅልዎን በድምጽ ትእዛዝ ይፍጠሩ',
      batch_no_match: 'ከማጣሪያዎ ጋር የሚዛመድ ጥቅል የለም',
      batch_details: 'የጥቅል ዝርዝሮች',
      batch_info: 'የጥቅል መረጃ',
      batch_quantity: 'መጠን',
      batch_variety: 'ዓይነት',
      batch_origin: 'መነሻ',
      batch_processing: 'ሂደት',
      batch_grade: 'ደረጃ',
      batch_status: 'ሁኔታ',
      batch_created: 'የተፈጠረ',
      batch_verified_date: 'የተረጋገጠ',
      batch_timeline: 'የጊዜ መስመር',

      /* ── Marketplace ─────────────────────── */
      market_title: 'ገበያ',
      market_tab_rfqs: 'ክፍት RFQ',
      market_tab_containers: 'የቤት ኮንቴይነሮች',
      market_tab_offers: 'የቤት ቅናሼች',
      market_search: 'RFQ ይፈልጉ...',
      market_all: 'ሁሉም',
      market_open: 'ክፍት',
      market_closed: 'ዝግ',
      market_arabica: 'አረቢካ',
      market_robusta: 'ሮቡስታ',
      market_empty: 'RFQ አልተገኘም',
      market_no_containers: 'እስካሁን ኮንቴይነር አልተዘገበም',
      market_no_containers_hint: 'የህብረት ስራዎ ኮንቴይነር እዚህ ይታያል',
      market_no_offers: 'እስካሁን ቅናሽ አልቀረበም',
      market_submit_offer: 'ቅናሽ ያስገቡ',
      market_quantity: 'መጠን (ኪ.ግ)',
      market_price: 'በኪ.ግ ዋጋ (USD)',
      market_delivery: 'የማድረስ ጊዜ (ቀናት)',
      market_notes: 'ተጨማሪ ማስታወሻዎች',
      market_notes_placeholder: 'አማራጭ ማስታወሻ...',
      market_submit: 'ቅናሽ ያስገቡ',
      market_success: 'ቅናሽዎ ቀርቧል!',
      market_offer_failed: 'ቅናሽ ማስገባት አልተሳካም',
      market_price_required: 'ዋጋ ያስፈልጋል',
      market_deadline: 'የጊዜ ገደብ',
      market_view: 'ዝርዝሮችን ይመልከቱ',
      market_buyer: 'ገዥ',
      market_your_price: 'የእርስዎ ዋጋ',
      market_rfq_details: 'የRFQ ዝርዝሮች',
      market_coffee_type: 'የቡና ዓይነት',
      market_target_price: 'የመዋያ ዋጋ',
      market_status: 'ሁኔታ',
      market_container_info: 'የኮንቴይነር መረጃ',
      market_grade: 'ደረጃ',
      market_processing: 'አቀናነብ',
      market_total: 'ድምር',
      market_sold: 'የተሸጠ',
      market_available_qty: 'የሚገኝ',
      market_listed: 'የተዘገበ',
      market_expires: 'የሚያልቅበት',
      market_fill_progress: 'የሚሎት ሁኔታ',
      market_buyers: 'ገዥዎች',
      market_pools: 'የግንብ ቡሎች',

      /* ── Trace ───────────────────────────── */
      trace_title: 'ቡና ይከታተሉ',
      trace_search: 'የጥቅል ID ወይም ሎት ቁጥር ይፈልጉ...',
      trace_empty_title: 'ጥቅል አልተመረጠም',
      trace_empty_desc: 'የክትትል መረጃ ለማየት ጥቅል ይምረጡ',
      trace_details: 'የጥቅል ዝርዝሮች',
      trace_journey: 'የጉዞ መስመር',
      trace_location: 'የአካባቢ ክትትል',
      trace_map_soon: 'ካርታ ቅርብ ይመጣል',
      trace_blockchain: 'ብሎክቼይን ማረጋገጫ',
      trace_tx_hash: 'የግብይት ሃሽ',
      trace_verified: 'በብሎክቼይን ተረጋግጧል',
      trace_not_anchored: 'እስካሁን አልተመዘገበም',
      trace_loading: 'የክትትል መረጃ በመጫን ላይ...',

      /* ── Profile ─────────────────────────── */
      profile_title: 'መገለጫዬ',
      profile_account: 'የመለያ መረጃ',
      profile_telegram_id: 'Telegram ID',
      profile_phone: 'ስልክ ቁጥር',
      profile_role: 'ሚና',
      profile_org: 'ድርጅት',
      profile_language: 'ቋንቋ',
      profile_not_set: 'አልተዘጋጀም',
      profile_none: 'የለም',
      profile_approved: 'ጸድቋል',

      /* ── Admin ───────────────────────────── */
      admin_title: 'የአስተዳዳሪ ቦርድ',
      admin_pending: 'በመጠባበቅ ላይ',
      admin_users: 'ተጠቃሚዎች',
      admin_rfqs: 'RFQs',
      admin_offers: 'ቅናሾች',
      admin_tab_registrations: 'ምዝገባዎች',
      admin_tab_users: 'ተጠቃሚዎች',
      admin_tab_rfqs: 'RFQs',
      admin_tab_offers: 'ቅናሾች',
      admin_approve: 'ያጽድቁ',
      admin_reject: 'ያልቃቁ',
      admin_name: 'ስም',
      admin_phone: 'ስልክ',
      admin_role: 'ሚና',
      admin_actions: 'ድርጊቶች',
      admin_status: 'ሁኔታ',
      admin_quantity: 'መጠን',
      admin_coffee_type: 'የቡና ዓይነት',
      admin_price: 'ዋጋ/ኪ.ግ',
      admin_cooperative: 'ህብረት ስራ',
      admin_no_pending: 'ምንም ጥበቃ ያለ ምዝገባ የለም',

      /* ── Common ──────────────────────────── */
      loading: 'በመጫን ላይ...',
      error: 'ስህተት',
      close: 'ዝጋ',
      back: 'ተመለስ',
      refresh: 'አድስ',
      english: 'EN',
      amharic: 'AM',
    },
  };

  let currentLang = localStorage.getItem('vl_lang') || 'en';

  function t(key) {
    return strings[currentLang]?.[key] || strings.en[key] || key;
  }

  function getLang() {
    return currentLang;
  }

  function setLang(lang) {
    currentLang = lang;
    localStorage.setItem('vl_lang', lang);
    translatePage();
    // Update toggle buttons
    document.querySelectorAll('.vl-lang-toggle button').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });
  }

  function translatePage() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const val = t(key);
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = val;
      } else {
        el.textContent = val;
      }
    });
  }

  // Auto-init: translate on DOMContentLoaded
  document.addEventListener('DOMContentLoaded', () => {
    translatePage();
    // Bind lang toggles
    document.querySelectorAll('.vl-lang-toggle button').forEach(btn => {
      btn.addEventListener('click', () => setLang(btn.dataset.lang));
      btn.classList.toggle('active', btn.dataset.lang === currentLang);
    });
  });

  return { t, getLang, setLang, translatePage };
})();
