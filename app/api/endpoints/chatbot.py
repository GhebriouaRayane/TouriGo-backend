import re
import unicodedata
from difflib import SequenceMatcher
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

Language = Literal["fr", "en", "ar"]


class ChatMessage(BaseModel):
    message: str
    context: Optional[str] = None  # "immobilier" | "vehicule" | "activite" | None
    language: Language = "fr"


class ChatResponse(BaseModel):
    reply: str
    suggestions: list[str]
    link: Optional[str] = None


def normalize_text(text: str) -> str:
    """Normalize text for FAQ matching."""
    lowered = text.lower()
    normalized = unicodedata.normalize("NFD", lowered)
    stripped = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    cleaned = re.sub(r"[^\w\s]", " ", stripped, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


STOPWORDS_BY_LANGUAGE: dict[Language, set[str]] = {
    "fr": {
        "comment", "pour", "je", "tu", "vous", "nous", "est", "ce", "que", "quoi", "quel",
        "quelle", "quels", "quelles", "puis", "dois", "mon", "ma", "mes", "ton", "ta",
        "tes", "votre", "vos", "un", "une", "des", "de", "du", "la", "le", "les", "au",
        "aux", "a", "à", "en", "sur", "avec", "dans", "et", "ou", "où", "qui", "si",
        "est-ce", "ceci", "cela",
    },
    "en": {
        "how", "do", "i", "you", "we", "is", "are", "the", "a", "an", "to", "of", "on",
        "in", "for", "can", "could", "should", "would", "my", "your", "our", "me", "us",
        "what", "which", "who", "where", "when",
    },
    "ar": {
        "كيف", "هل", "انا", "أنا", "انت", "أنت", "هو", "هي", "هم", "نحن", "ما", "ماذا",
        "من", "أين", "اين", "متى", "في", "على", "الى", "إلى", "عن", "و", "او", "أو",
        "هذا", "هذه", "ذلك", "تلك", "يمكن", "أستطيع", "استطيع", "ارجو", "من", "فضلك",
        "ال",
    },
}


SYNONYMS_BY_LANGUAGE: dict[Language, dict[str, set[str]]] = {
    "fr": {
        "reserver": {"reservation", "booking", "booker"},
        "reservation": {"reserver", "booking", "book"},
        "paiement": {"payer", "payment", "reglement"},
        "payer": {"paiement", "payment"},
        "annonce": {"listing", "publication", "post"},
        "publier": {"publication", "poster"},
        "publication": {"publier", "annonce", "listing"},
        "modifier": {"changer", "editer", "update"},
        "changer": {"modifier", "editer", "update"},
        "supprimer": {"effacer", "delete", "retirer"},
        "profil": {"compte"},
        "compte": {"profil"},
        "connexion": {"login", "connecter"},
        "inscription": {"register", "signup"},
        "support": {"aide", "assistance", "contact"},
        "aide": {"support", "assistance"},
        "favoris": {"favori", "favorite"},
        "favori": {"favoris", "favorite"},
        "filtrer": {"filtre", "filter"},
        "filtre": {"filtrer", "filter"},
        "langue": {"language"},
        "disponibilite": {"disponibilites", "calendrier", "planning"},
        "covoiturage": {"carpool", "trajet"},
        "vehicule": {"voiture", "auto", "car"},
        "logement": {"immobilier", "hebergement", "accommodation"},
        "activite": {"loisir", "experience"},
        "avis": {"review", "note", "commentaire"},
        "annuler": {"cancel", "annulation"},
        "hote": {"host"},
    },
    "en": {
        "book": {"reserve", "reservation", "booking"},
        "booking": {"book", "reserve", "reservation"},
        "reservation": {"book", "reserve", "booking"},
        "listing": {"ad", "post", "publication"},
        "publish": {"post", "publication"},
        "edit": {"change", "update", "modify"},
        "modify": {"edit", "change", "update"},
        "delete": {"remove", "cancel"},
        "support": {"help", "assistance", "contact"},
        "favorite": {"favourite", "wishlist", "save", "saved"},
        "favourite": {"favorite", "wishlist"},
        "filter": {"filters", "refine"},
        "filters": {"filter"},
        "login": {"signin", "sign"},
        "signin": {"login", "sign"},
        "signup": {"register", "sign"},
        "register": {"signup", "sign"},
        "language": {"locale"},
        "availability": {"calendar", "schedule"},
        "carpool": {"rideshare", "ride"},
        "vehicle": {"car", "auto"},
        "accommodation": {"lodging", "housing", "home"},
        "host": {"owner"},
    },
    "ar": {
        "حجز": {"حجوزات", "احجز", "حجزي"},
        "حجوزات": {"حجز"},
        "الغاء": {"إلغاء", "الغاء"},
        "اعلان": {"إعلان", "منشور", "نشر"},
        "نشر": {"اعلان", "منشور"},
        "تعديل": {"تغيير", "تحديث"},
        "دعم": {"مساعدة", "مساندة"},
        "مضيف": {"مستضيف"},
        "مفضلة": {"مفضلات", "تفضيل"},
        "مفضلات": {"مفضلة"},
        "تصفية": {"فلترة"},
        "فلترة": {"تصفية"},
        "تسجيل": {"دخول"},
        "دخول": {"تسجيل"},
        "لغة": {"اللغة"},
        "توفر": {"توافر", "متاح"},
    },
}


def tokenize(text: str, language: Language) -> list[str]:
    normalized = normalize_text(text)
    tokens = normalized.split()
    stopwords = STOPWORDS_BY_LANGUAGE.get(language, set())
    base_tokens = [token for token in tokens if token not in stopwords]
    synonyms = SYNONYMS_BY_LANGUAGE.get(language, {})
    expanded: set[str] = set(base_tokens)
    for token in base_tokens:
        expanded.update(synonyms.get(token, set()))
    return [token for token in expanded if token]


def char_ngrams(text: str, n: int = 3) -> set[str]:
    if len(text) <= n:
        return {text} if text else set()
    return {text[index : index + n] for index in range(len(text) - n + 1)}


def partial_ratio(short: str, long: str) -> float:
    if not short or not long:
        return 0.0
    if len(short) > len(long):
        short, long = long, short
    if len(short) == len(long):
        return SequenceMatcher(None, short, long, autojunk=False).ratio()

    best = 0.0
    window = len(short)
    for index in range(len(long) - window + 1):
        ratio = SequenceMatcher(None, short, long[index : index + window], autojunk=False).ratio()
        if ratio > best:
            best = ratio
            if best >= 0.98:
                break
    return best


def similarity_score(
    message_norm: str,
    question_norm: str,
    message_tokens: set[str],
    question_tokens: set[str],
) -> tuple[float, int]:
    if not message_norm or not question_norm:
        return 0.0, 0

    seq_ratio = SequenceMatcher(None, message_norm, question_norm, autojunk=False).ratio()
    partial = partial_ratio(message_norm, question_norm)

    message_grams = char_ngrams(message_norm)
    question_grams = char_ngrams(question_norm)
    grams_union = len(message_grams | question_grams)
    grams_intersection = len(message_grams & question_grams)
    trigram_jaccard = grams_intersection / grams_union if grams_union else 0.0

    intersection = len(message_tokens & question_tokens)
    union = len(message_tokens | question_tokens)
    token_jaccard = intersection / union if union else 0.0
    token_containment = (
        intersection / max(len(message_tokens), len(question_tokens))
        if message_tokens and question_tokens
        else 0.0
    )

    base = max(seq_ratio, partial, trigram_jaccard, 0.6 * token_jaccard + 0.4 * token_containment)
    base = min(1.0, base + 0.07 * min(intersection, 4))
    if question_norm in message_norm or message_norm in question_norm:
        base = max(base, 0.95)
    return base, intersection


def should_accept_match(
    score: float,
    overlap: int,
    message_tokens_count: int,
    raw_tokens_count: int,
) -> bool:
    if raw_tokens_count <= 1:
        return False
    if score >= 0.92 and overlap >= 1:
        return True
    if score >= 0.86 and overlap >= 2:
        return True
    if score >= 0.8 and overlap >= 3:
        return True
    if message_tokens_count >= 6 and overlap >= 2 and score >= 0.74:
        return True
    return False


def build_faq_index() -> list[dict]:
    index: list[dict] = []
    for entry in FAQ_ENTRIES:
        languages_block: dict[str, dict] = {}
        for lang, questions in entry["questions"].items():
            texts = [normalize_text(question) for question in questions]
            tokens = [set(tokenize(question, lang)) for question in questions]
            union: set[str] = set()
            for token_set in tokens:
                union.update(token_set)
            languages_block[lang] = {"texts": texts, "tokens": tokens, "union": union}
        index.append(
            {
                "key": entry["key"],
                "answers": entry["answers"],
                "link": entry.get("link"),
                "suggestions": entry.get("suggestions"),
                "questions": languages_block,
            }
        )
    return index


FAQ_SUGGESTIONS_BY_LANGUAGE: dict[Language, list[str]] = {
    "fr": ["❓ Aide", "🏠 Immobilier", "🚗 Véhicules", "🌴 Activités"],
    "en": ["❓ Help", "🏠 Real estate", "🚗 Vehicles", "🌴 Activities"],
    "ar": ["❓ مساعدة", "🏠 العقارات", "🚗 المركبات", "🌴 الأنشطة"],
}

FAQ_ENTRIES = [
    {
        "key": "reserve_service",
        "questions": {
            "fr": ["Comment réserver un service sur Tourigo ?"],
            "en": ["How do I book a service on Tourigo?"],
            "ar": ["كيف أحجز خدمة على Tourigo؟"],
        },
        "answers": {
            "fr": (
                "Pour réserver un service, choisissez l’annonce qui vous intéresse, "
                "sélectionnez la date et l’heure du rendez-vous (RDV) puis confirmez "
                "votre réservation directement dans l’application."
            ),
            "en": (
                "To book a service, choose the listing you are interested in, "
                "select the appointment date and time, then confirm your booking "
                "directly in the app."
            ),
            "ar": (
                "لحجز خدمة، اختر الإعلان الذي يهمك، حدّد تاريخ ووقت الموعد "
                "ثم أكّد الحجز مباشرة داخل التطبيق."
            ),
        },
    },
    {
        "key": "account_required",
        "questions": {
            "fr": ["Dois-je créer un compte pour réserver ?"],
            "en": ["Do I need to create an account to book?"],
            "ar": ["هل يجب إنشاء حساب للحجز؟"],
        },
        "answers": {
            "fr": (
                "Oui, vous devez créer un compte utilisateur pour pouvoir réserver "
                "des services, contacter les hôtes et gérer vos réservations."
            ),
            "en": (
                "Yes, you must create a user account to book services, contact hosts, "
                "and manage your reservations."
            ),
            "ar": (
                "نعم، يجب إنشاء حساب مستخدم حتى تتمكن من حجز الخدمات والتواصل "
                "مع المضيفين وإدارة حجوزاتك."
            ),
        },
    },
    {
        "key": "payment_reservation",
        "questions": {
            "fr": ["Comment payer une réservation ?"],
            "en": ["How do I pay for a reservation?"],
            "ar": ["كيف أدفع ثمن الحجز؟"],
        },
        "answers": {
            "fr": (
                "Vous pouvez payer directement en ligne via l’application ou en espèces "
                "lors de l’accès au service, selon votre préférence."
            ),
            "en": (
                "You can pay online through the app or in cash when accessing the service, "
                "depending on your preference."
            ),
            "ar": (
                "يمكنك الدفع مباشرة عبر التطبيق أو نقدًا عند الوصول إلى الخدمة، "
                "حسب تفضيلك."
            ),
        },
    },
    {
        "key": "become_host",
        "questions": {
            "fr": ["Comment devenir hôte ?"],
            "en": ["How do I become a host?"],
            "ar": ["كيف أصبح مضيفًا؟"],
        },
        "answers": {
            "fr": (
                "Pour devenir hôte, vous devez créer un compte hôte depuis votre profil "
                "et compléter les informations nécessaires pour pouvoir proposer vos services."
            ),
            "en": (
                "To become a host, you need to create a host account from your profile "
                "and complete the required information to offer your services."
            ),
            "ar": (
                "لتصبح مضيفًا، أنشئ حساب مضيف من ملفك الشخصي وأكمل المعلومات اللازمة "
                "لتتمكن من عرض خدماتك."
            ),
        },
    },
    {
        "key": "publish_listing",
        "questions": {
            "fr": ["Comment publier une annonce ?"],
            "en": ["How do I publish a listing?"],
            "ar": ["كيف أنشر إعلانًا؟"],
        },
        "answers": {
            "fr": (
                "Une fois votre compte hôte activé, vous pouvez publier une annonce "
                "en ajoutant une description du service, des photos, un prix et vos disponibilités."
            ),
            "en": (
                "Once your host account is activated, you can publish a listing by adding "
                "a service description, photos, a price, and your availability."
            ),
            "ar": (
                "بعد تفعيل حساب المضيف، يمكنك نشر إعلان بإضافة وصف للخدمة وصور "
                "وسعر وتوفّر المواعيد."
            ),
        },
    },
    {
        "key": "host_definition",
        "questions": {
            "fr": ["Qu’est-ce qu’un hôte ?"],
            "en": ["What is a host?"],
            "ar": ["ما هو المضيف؟"],
        },
        "answers": {
            "fr": (
                "Un hôte est une personne qui propose un service sur Tourigo, "
                "comme un logement, un véhicule, un trajet de covoiturage ou une activité."
            ),
            "en": (
                "A host is a person who offers a service on Tourigo, such as accommodation, "
                "a vehicle, a carpool ride, or an activity."
            ),
            "ar": (
                "المضيف هو شخص يقدّم خدمة على Tourigo مثل سكن أو مركبة "
                "أو مرافقة بالسيارة أو نشاط."
            ),
        },
    },
    {
        "key": "contact_host",
        "questions": {
            "fr": ["Comment contacter un hôte ?"],
            "en": ["How do I contact a host?"],
            "ar": ["كيف أتواصل مع مضيف؟"],
        },
        "answers": {
            "fr": (
                "Vous pouvez contacter un hôte via le chat intégré dans l’application "
                "ou par téléphone si le numéro est disponible sur l’annonce."
            ),
            "en": (
                "You can contact a host via the in-app chat or by phone if the number "
                "is available on the listing."
            ),
            "ar": (
                "يمكنك التواصل مع المضيف عبر الدردشة داخل التطبيق أو بالهاتف "
                "إذا كان الرقم متاحًا في الإعلان."
            ),
        },
    },
    {
        "key": "modify_appointment",
        "questions": {
            "fr": ["Comment modifier mon rendez-vous ?"],
            "en": ["How do I change my appointment?"],
            "ar": ["كيف أعدّل موعدي؟"],
        },
        "answers": {
            "fr": (
                "Pour modifier votre RDV, allez dans Mes réservations, "
                "sélectionnez la réservation concernée puis changez la date "
                "ou l’heure du rendez-vous."
            ),
            "en": (
                "To change your appointment, go to My reservations, "
                "select the reservation, then change the date or time."
            ),
            "ar": (
                "لتعديل موعدك، اذهب إلى «حجوزاتي»، اختر الحجز المعني "
                "ثم غيّر تاريخ أو وقت الموعد."
            ),
        },
    },
    {
        "key": "cancel_reservation",
        "questions": {
            "fr": ["Comment annuler une réservation ?"],
            "en": ["How do I cancel a reservation?"],
            "ar": ["كيف ألغي حجزًا؟"],
        },
        "answers": {
            "fr": (
                "Pour annuler une réservation, allez dans Mes réservations, "
                "sélectionnez la réservation puis cliquez sur Annuler."
            ),
            "en": (
                "To cancel a reservation, go to My reservations, "
                "select the reservation, then click Cancel."
            ),
            "ar": (
                "لإلغاء الحجز، اذهب إلى «حجوزاتي»، اختر الحجز ثم اضغط على «إلغاء»."
            ),
        },
    },
    {
        "key": "tourigo_security",
        "questions": {
            "fr": ["Est-ce que Tourigo est sécurisé ?"],
            "en": ["Is Tourigo secure?"],
            "ar": ["هل Tourigo آمن؟"],
        },
        "answers": {
            "fr": (
                "Oui, Tourigo met en place un système de sécurité étatique "
                "et une vérification des comptes afin de garantir la sécurité des utilisateurs."
            ),
            "en": (
                "Yes, Tourigo implements a state-level security system "
                "and account verification to ensure user safety."
            ),
            "ar": (
                "نعم، يطبّق Tourigo نظام أمان على مستوى الدولة "
                "والتحقق من الحسابات لضمان سلامة المستخدمين."
            ),
        },
    },
    {
        "key": "services_available",
        "questions": {
            "fr": ["Quels services peut-on trouver sur Tourigo ?"],
            "en": ["What services can I find on Tourigo?"],
            "ar": ["ما الخدمات المتوفرة على Tourigo؟"],
        },
        "answers": {
            "fr": (
                "Sur Tourigo, vous pouvez trouver des logements, du covoiturage, "
                "des locations de véhicules et différentes activités ou loisirs."
            ),
            "en": (
                "On Tourigo, you can find accommodations, carpooling, "
                "vehicle rentals, and various activities or leisure."
            ),
            "ar": (
                "على Tourigo يمكنك العثور على سكن، ومرافقة بالسيارة، "
                "وتأجير مركبات، وأنشطة أو ترفيه متنوعة."
            ),
        },
    },
    {
        "key": "multiple_services",
        "questions": {
            "fr": ["Puis-je réserver plusieurs services ?"],
            "en": ["Can I book multiple services?"],
            "ar": ["هل يمكنني حجز عدة خدمات؟"],
        },
        "answers": {
            "fr": (
                "Oui, vous pouvez réserver plusieurs services différents selon vos besoins "
                "et les disponibilités des hôtes."
            ),
            "en": (
                "Yes, you can book several different services depending on your needs "
                "and host availability."
            ),
            "ar": (
                "نعم، يمكنك حجز عدة خدمات مختلفة حسب احتياجاتك "
                "وتوفّر المضيفين."
            ),
        },
    },
    {
        "key": "view_reservations",
        "questions": {
            "fr": ["Comment voir mes réservations ?"],
            "en": ["How do I see my reservations?"],
            "ar": ["كيف أرى حجوزاتي؟"],
        },
        "answers": {
            "fr": (
                "Toutes vos réservations sont visibles dans la section Mes réservations "
                "de votre compte utilisateur."
            ),
            "en": (
                "All your reservations are visible in the My reservations section "
                "of your user account."
            ),
            "ar": (
                "جميع حجوزاتك تظهر في قسم «حجوزاتي» ضمن حسابك."
            ),
        },
    },
    {
        "key": "talk_before_booking",
        "questions": {
            "fr": ["Puis-je parler avec l’hôte avant de réserver ?"],
            "en": ["Can I talk to the host before booking?"],
            "ar": ["هل يمكنني التحدث مع المضيف قبل الحجز؟"],
        },
        "answers": {
            "fr": (
                "Oui, vous pouvez envoyer un message via le chat de l’application "
                "ou appeler l’hôte avant de confirmer votre réservation."
            ),
            "en": (
                "Yes, you can send a message via the app chat or call the host "
                "before confirming your booking."
            ),
            "ar": (
                "نعم، يمكنك إرسال رسالة عبر دردشة التطبيق أو الاتصال بالمضيف "
                "قبل تأكيد الحجز."
            ),
        },
    },
    {
        "key": "edit_profile",
        "questions": {
            "fr": ["Comment modifier mon profil ?"],
            "en": ["How do I edit my profile?"],
            "ar": ["كيف أعدّل ملفي الشخصي؟"],
        },
        "answers": {
            "fr": (
                "Pour modifier votre profil, allez dans Mon profil puis changez vos "
                "informations personnelles si nécessaire."
            ),
            "en": (
                "To edit your profile, go to My profile and change your personal "
                "information if needed."
            ),
            "ar": (
                "لتعديل ملفك، اذهب إلى «ملفي الشخصي» ثم غيّر معلوماتك عند الحاجة."
            ),
        },
    },
    {
        "key": "delete_account",
        "questions": {
            "fr": ["Comment supprimer mon compte ?"],
            "en": ["How do I delete my account?"],
            "ar": ["كيف أحذف حسابي؟"],
        },
        "answers": {
            "fr": (
                "Vous pouvez supprimer votre compte depuis les paramètres de votre profil "
                "dans l’application."
            ),
            "en": (
                "You can delete your account from your profile settings in the app."
            ),
            "ar": (
                "يمكنك حذف حسابك من إعدادات ملفك الشخصي داخل التطبيق."
            ),
        },
    },
    {
        "key": "add_photos_listing",
        "questions": {
            "fr": ["Comment ajouter des photos à mon annonce ?"],
            "en": ["How do I add photos to my listing?"],
            "ar": ["كيف أضيف صورًا إلى إعلاني؟"],
        },
        "answers": {
            "fr": (
                "Depuis votre espace hôte, ouvrez votre annonce puis ajoutez "
                "ou modifiez les photos pour présenter votre service."
            ),
            "en": (
                "From your host space, open your listing then add or edit photos "
                "to showcase your service."
            ),
            "ar": (
                "من مساحة المضيف، افتح إعلانك ثم أضف أو عدّل الصور لعرض خدمتك."
            ),
        },
    },
    {
        "key": "change_listing_price",
        "questions": {
            "fr": ["Comment changer le prix de mon annonce ?"],
            "en": ["How do I change the price of my listing?"],
            "ar": ["كيف أغيّر سعر إعلاني؟"],
        },
        "answers": {
            "fr": (
                "Dans votre espace hôte, sélectionnez l’annonce concernée puis "
                "modifiez le prix selon vos préférences."
            ),
            "en": (
                "In your host space, select the listing and then edit the price "
                "as you prefer."
            ),
            "ar": (
                "في مساحة المضيف، اختر الإعلان ثم عدّل السعر حسب تفضيلاتك."
            ),
        },
    },
    {
        "key": "reservation_confirmed",
        "questions": {
            "fr": ["Comment savoir si une réservation est confirmée ?"],
            "en": ["How do I know if a reservation is confirmed?"],
            "ar": ["كيف أعرف أن الحجز تم تأكيده؟"],
        },
        "answers": {
            "fr": (
                "Vous recevrez une notification dans l’application lorsque votre "
                "réservation est confirmée."
            ),
            "en": (
                "You will receive a notification in the app when your reservation "
                "is confirmed."
            ),
            "ar": (
                "ستتلقى إشعارًا داخل التطبيق عندما يتم تأكيد الحجز."
            ),
        },
    },
    {
        "key": "leave_review",
        "questions": {
            "fr": ["Puis-je laisser un avis ?"],
            "en": ["Can I leave a review?"],
            "ar": ["هل يمكنني ترك تقييم؟"],
        },
        "answers": {
            "fr": (
                "Oui, après le service vous pouvez laisser une note et un commentaire "
                "pour partager votre expérience."
            ),
            "en": (
                "Yes, after the service you can leave a rating and a comment "
                "to share your experience."
            ),
            "ar": (
                "نعم، بعد الخدمة يمكنك ترك تقييم وتعليق لمشاركة تجربتك."
            ),
        },
    },
    {
        "key": "view_host_reviews",
        "questions": {
            "fr": ["Comment voir les avis d’un hôte ?"],
            "en": ["How do I see a host's reviews?"],
            "ar": ["كيف أرى تقييمات المضيف؟"],
        },
        "answers": {
            "fr": (
                "Les avis des utilisateurs sont visibles directement sur le profil "
                "ou l’annonce de l’hôte."
            ),
            "en": (
                "User reviews are visible directly on the host's profile or listing."
            ),
            "ar": (
                "تقييمات المستخدمين تظهر مباشرة في ملف المضيف أو الإعلان."
            ),
        },
    },
    {
        "key": "problem_reservation",
        "questions": {
            "fr": ["Que faire si j’ai un problème avec une réservation ?"],
            "en": ["What should I do if I have a problem with a reservation?"],
            "ar": ["ماذا أفعل إذا واجهت مشكلة في الحجز؟"],
        },
        "answers": {
            "fr": (
                "En cas de problème, vous pouvez contacter l’hôte ou le support "
                "Tourigo via l’application."
            ),
            "en": (
                "If there is a problem, you can contact the host or Tourigo support "
                "via the app."
            ),
            "ar": (
                "في حال وجود مشكلة، يمكنك التواصل مع المضيف أو دعم Tourigo عبر التطبيق."
            ),
        },
    },
    {
        "key": "carpool_driver",
        "questions": {
            "fr": ["Comment devenir conducteur pour le covoiturage ?"],
            "en": ["How do I become a driver for carpooling?"],
            "ar": ["كيف أصبح سائقًا للمرافقة بالسيارة؟"],
        },
        "answers": {
            "fr": (
                "Pour proposer un trajet, vous devez créer une annonce de covoiturage "
                "en indiquant la destination, la date et le nombre de places disponibles."
            ),
            "en": (
                "To offer a ride, you need to create a carpool listing by specifying "
                "the destination, date, and number of available seats."
            ),
            "ar": (
                "لعرض رحلة، أنشئ إعلان مرافقة بالسيارة مع تحديد الوجهة والتاريخ "
                "وعدد المقاعد المتاحة."
            ),
        },
    },
    {
        "key": "carpool_book_seat",
        "questions": {
            "fr": ["Comment réserver une place en covoiturage ?"],
            "en": ["How do I book a carpool seat?"],
            "ar": ["كيف أحجز مقعدًا في المرافقة بالسيارة؟"],
        },
        "answers": {
            "fr": (
                "Choisissez le trajet qui vous intéresse puis réservez votre place "
                "directement dans l’application."
            ),
            "en": (
                "Choose the ride you are interested in and book your seat directly "
                "in the app."
            ),
            "ar": (
                "اختر الرحلة التي تهمك ثم احجز مقعدك مباشرة داخل التطبيق."
            ),
        },
    },
    {
        "key": "find_service_city",
        "questions": {
            "fr": ["Comment trouver un service dans ma ville ?"],
            "en": ["How do I find a service in my city?"],
            "ar": ["كيف أجد خدمة في مدينتي؟"],
        },
        "answers": {
            "fr": (
                "Utilisez la barre de recherche et indiquez votre ville pour voir "
                "les services disponibles autour de vous."
            ),
            "en": (
                "Use the search bar and enter your city to see the services available nearby."
            ),
            "ar": (
                "استخدم شريط البحث وأدخل مدينتك لرؤية الخدمات المتاحة حولك."
            ),
        },
    },
    {
        "key": "edit_listing_after_publish",
        "questions": {
            "fr": ["Puis-je modifier mon annonce après publication ?"],
            "en": ["Can I edit my listing after publishing?"],
            "ar": ["هل يمكنني تعديل إعلاني بعد النشر؟"],
        },
        "answers": {
            "fr": (
                "Oui, vous pouvez modifier votre annonce à tout moment "
                "depuis votre espace hôte."
            ),
            "en": (
                "Yes, you can edit your listing at any time from your host space."
            ),
            "ar": (
                "نعم، يمكنك تعديل إعلانك في أي وقت من مساحة المضيف."
            ),
        },
    },
    {
        "key": "who_can_publish",
        "questions": {
            "fr": ["Qui peut publier une annonce ?"],
            "en": ["Who can publish a listing?"],
            "ar": ["من يمكنه نشر إعلان؟"],
        },
        "answers": {
            "fr": (
                "Seuls les utilisateurs qui deviennent hôtes et créent un compte hôte "
                "peuvent publier des annonces."
            ),
            "en": (
                "Only users who become hosts and create a host account can publish listings."
            ),
            "ar": (
                "فقط المستخدمون الذين أصبحوا مضيفين وأنشؤوا حساب مضيف "
                "يمكنهم نشر الإعلانات."
            ),
        },
    },
    {
        "key": "host_payment_receive",
        "questions": {
            "fr": ["Comment recevoir les paiements en tant qu’hôte ?"],
            "en": ["How do I receive payments as a host?"],
            "ar": ["كيف أستلم المدفوعات كمضيف؟"],
        },
        "answers": {
            "fr": (
                "Les paiements peuvent être reçus en ligne via la plateforme ou en espèces "
                "lors de l’accès au service."
            ),
            "en": (
                "Payments can be received online via the platform or in cash "
                "when accessing the service."
            ),
            "ar": (
                "يمكن استلام المدفوعات عبر المنصة أو نقدًا عند الوصول إلى الخدمة."
            ),
        },
    },
    {
        "key": "tourigo_mobile",
        "questions": {
            "fr": ["Est-ce que Tourigo fonctionne sur téléphone ?"],
            "en": ["Does Tourigo work on a phone?"],
            "ar": ["هل يعمل Tourigo على الهاتف؟"],
        },
        "answers": {
            "fr": (
                "Oui, Tourigo est disponible sur application mobile et sur site web."
            ),
            "en": (
                "Yes, Tourigo is available as a mobile app and on the website."
            ),
            "ar": (
                "نعم، Tourigo متوفر كتطبيق للهاتف وعلى الموقع الإلكتروني."
            ),
        },
    },
    {
        "key": "contact_support",
        "questions": {
            "fr": ["Comment contacter le support Tourigo ?"],
            "en": ["How do I contact Tourigo support?"],
            "ar": ["كيف أتواصل مع دعم Tourigo؟"],
        },
        "answers": {
            "fr": (
                "Vous pouvez contacter le support directement depuis l’application "
                "ou via le formulaire de contact du site."
            ),
            "en": (
                "You can contact support directly from the app or via the website "
                "contact form."
            ),
            "ar": (
                "يمكنك التواصل مع الدعم مباشرة من التطبيق أو عبر نموذج الاتصال في الموقع."
            ),
        },
    },
    {
        "key": "login_how",
        "questions": {
            "fr": ["Comment se connecter ?"],
            "en": ["How do I log in?"],
            "ar": ["كيف أسجل الدخول؟"],
        },
        "answers": {
            "fr": (
                "Allez sur Connexion, choisissez l'email ou le téléphone, "
                "saisissez vos informations puis validez."
            ),
            "en": (
                "Go to Log in, choose email or phone, "
                "enter your details, then submit."
            ),
            "ar": (
                "اذهب إلى تسجيل الدخول، اختر البريد الإلكتروني أو الهاتف، "
                "أدخل بياناتك ثم أكّد."
            ),
        },
    },
    {
        "key": "signup_how",
        "questions": {
            "fr": ["Comment s'inscrire ?"],
            "en": ["How do I sign up?"],
            "ar": ["كيف أنشئ حسابًا؟"],
        },
        "answers": {
            "fr": (
                "Allez sur Inscription, choisissez l'email ou le téléphone, "
                "remplissez les informations puis confirmez le code reçu."
            ),
            "en": (
                "Go to Sign up, choose email or phone, "
                "fill in the details, then confirm the verification code."
            ),
            "ar": (
                "اذهب إلى إنشاء حساب، اختر البريد أو الهاتف، "
                "أدخل المعلومات ثم أكّد رمز التحقق."
            ),
        },
    },
    {
        "key": "signup_methods",
        "questions": {
            "fr": ["Puis-je m'inscrire avec email ou téléphone ?"],
            "en": ["Can I sign up with email or phone?"],
            "ar": ["هل يمكنني التسجيل بالبريد الإلكتروني أو الهاتف؟"],
        },
        "answers": {
            "fr": "Oui, les deux options sont disponibles.",
            "en": "Yes, both options are available.",
            "ar": "نعم، الخياران متاحان.",
        },
    },
    {
        "key": "activate_host_account",
        "questions": {
            "fr": ["Comment activer mon compte hôte ?"],
            "en": ["How do I activate my host account?"],
            "ar": ["كيف أفعّل حساب المضيف؟"],
        },
        "answers": {
            "fr": (
                "Depuis votre profil ou la page Devenir hôte, "
                "activez le statut hôte. Une fois activé, vous pouvez publier."
            ),
            "en": (
                "From your profile or the Become a host page, "
                "activate host status. Once active, you can publish listings."
            ),
            "ar": (
                "من ملفك الشخصي أو صفحة أصبح مضيفًا، "
                "فعّل حالة المضيف. بعد التفعيل يمكنك نشر الإعلانات."
            ),
        },
    },
    {
        "key": "view_listings",
        "questions": {
            "fr": ["Comment voir mes annonces ?"],
            "en": ["How do I view my listings?"],
            "ar": ["كيف أرى إعلاناتي؟"],
        },
        "answers": {
            "fr": "Dans votre tableau de bord/ espace hôte, ouvrez l'onglet Mes annonces.",
            "en": "In your dashboard/host space, open the My listings tab.",
            "ar": "من لوحة التحكم/مساحة المضيف، افتح تبويب إعلاناتي.",
        },
    },
    {
        "key": "delete_listing",
        "questions": {
            "fr": ["Comment supprimer une annonce ?"],
            "en": ["How do I delete a listing?"],
            "ar": ["كيف أحذف إعلانًا؟"],
        },
        "answers": {
            "fr": (
                "Dans votre espace hôte, ouvrez l'annonce puis choisissez Supprimer "
                "et confirmez."
            ),
            "en": (
                "In your host space, open the listing, choose Delete, and confirm."
            ),
            "ar": (
                "في مساحة المضيف، افتح الإعلان ثم اختر حذف وأكّد."
            ),
        },
    },
    {
        "key": "add_favorite",
        "questions": {
            "fr": ["Comment ajouter une annonce aux favoris ?"],
            "en": ["How do I add a listing to favorites?"],
            "ar": ["كيف أضيف إعلانًا إلى المفضلة؟"],
        },
        "answers": {
            "fr": (
                "Cliquez sur l'icône cœur d'une annonce pour l'ajouter à vos favoris."
            ),
            "en": (
                "Click the heart icon on a listing to add it to your favorites."
            ),
            "ar": (
                "اضغط على أيقونة القلب في الإعلان لإضافته إلى المفضلة."
            ),
        },
    },
    {
        "key": "view_favorites",
        "questions": {
            "fr": ["Où trouver mes favoris ?"],
            "en": ["Where can I find my favorites?"],
            "ar": ["أين أجد المفضلة؟"],
        },
        "answers": {
            "fr": "Dans votre tableau de bord, ouvrez l'onglet Favoris.",
            "en": "In your dashboard, open the Favorites tab.",
            "ar": "من لوحة التحكم، افتح تبويب المفضلة.",
        },
    },
    {
        "key": "filter_results",
        "questions": {
            "fr": ["Comment filtrer les résultats ?"],
            "en": ["How do I filter results?"],
            "ar": ["كيف أفلتر النتائج؟"],
        },
        "answers": {
            "fr": (
                "Utilisez les filtres et la recherche (ville, prix, dates, type) "
                "pour affiner les résultats."
            ),
            "en": (
                "Use the filters and search (city, price, dates, type) "
                "to refine the results."
            ),
            "ar": (
                "استخدم الفلاتر والبحث (المدينة، السعر، التواريخ، النوع) "
                "لتضييق النتائج."
            ),
        },
    },
    {
        "key": "listing_types",
        "questions": {
            "fr": ["Quels types d'annonces puis-je publier ?"],
            "en": ["What types of listings can I publish?"],
            "ar": ["ما أنواع الإعلانات التي يمكنني نشرها؟"],
        },
        "answers": {
            "fr": (
                "Vous pouvez publier des logements, des véhicules "
                "(location ou covoiturage) et des activités."
            ),
            "en": (
                "You can publish accommodations, vehicles "
                "(rental or carpool), and activities."
            ),
            "ar": (
                "يمكنك نشر سكن، مركبات (تأجير أو مرافقة بالسيارة)، وأنشطة."
            ),
        },
    },
    {
        "key": "change_language",
        "questions": {
            "fr": ["Comment changer la langue de l'application ?"],
            "en": ["How do I change the app language?"],
            "ar": ["كيف أغير لغة التطبيق؟"],
        },
        "answers": {
            "fr": (
                "Utilisez le sélecteur de langue dans le menu "
                "(Français, English, العربية)."
            ),
            "en": (
                "Use the language selector in the menu "
                "(Français, English, العربية)."
            ),
            "ar": (
                "استخدم محدد اللغة في القائمة "
                "(Français, English, العربية)."
            ),
        },
    },
    {
        "key": "secure_payment",
        "questions": {
            "fr": ["Le paiement est-il sécurisé ?"],
            "en": ["Is payment secure?"],
            "ar": ["هل الدفع آمن؟"],
        },
        "answers": {
            "fr": "Oui, les paiements sont protégés par nos protocoles de sécurité.",
            "en": "Yes, payments are protected by our security protocols.",
            "ar": "نعم، المدفوعات محمية ببروتوكولات الأمان لدينا.",
        },
    },
    {
        "key": "help_center",
        "questions": {
            "fr": ["Où trouver le centre d'aide ?"],
            "en": ["Where can I find the help center?"],
            "ar": ["أين أجد مركز المساعدة؟"],
        },
        "answers": {
            "fr": "Dans le menu ou le pied de page, ouvrez Centre d'aide.",
            "en": "In the menu or footer, open the Help Center.",
            "ar": "في القائمة أو أسفل الصفحة، افتح مركز المساعدة.",
        },
    },
    {
        "key": "update_availability",
        "questions": {
            "fr": ["Comment modifier les disponibilités d'une annonce ?"],
            "en": ["How do I update a listing's availability?"],
            "ar": ["كيف أعدّل توافر إعلان؟"],
        },
        "answers": {
            "fr": (
                "Dans votre espace hôte, éditez l'annonce "
                "et mettez à jour vos disponibilités."
            ),
            "en": (
                "In your host space, edit the listing "
                "and update availability."
            ),
            "ar": (
                "في مساحة المضيف، حرّر الإعلان وحدّث التوافر."
            ),
        },
    },
]

FAQ_INDEX = build_faq_index()


def match_faq(message: str, language: Language) -> Optional[ChatResponse]:
    """Try to match a FAQ entry before running intent detection."""
    if not message or not message.strip():
        return None
    message_norm = normalize_text(message)
    if not message_norm:
        return None
    raw_tokens = message_norm.split()
    if len(raw_tokens) <= 1:
        return None

    languages_to_check: list[Language] = []
    for lang in (language, "fr", "en", "ar"):
        if lang not in languages_to_check:
            languages_to_check.append(lang)

    best_entry: Optional[dict] = None
    best_score = 0.0
    best_overlap = 0
    best_message_tokens_count = 0

    message_tokens_by_language: dict[Language, set[str]] = {
        lang: set(tokenize(message_norm, lang)) for lang in languages_to_check
    }

    for entry in FAQ_INDEX:
        for lang in languages_to_check:
            lang_block = entry["questions"].get(lang)
            if not lang_block:
                continue
            message_tokens = message_tokens_by_language[lang]
            message_tokens_count = len(message_tokens)
            for index, question_norm in enumerate(lang_block["texts"]):
                question_tokens = lang_block["tokens"][index]
                score, overlap = similarity_score(
                    message_norm,
                    question_norm,
                    message_tokens,
                    question_tokens,
                )
                if score > best_score or (abs(score - best_score) < 0.01 and overlap > best_overlap):
                    best_score = score
                    best_overlap = overlap
                    best_entry = entry
                    best_message_tokens_count = message_tokens_count

    if best_entry is not None and should_accept_match(
        best_score,
        best_overlap,
        best_message_tokens_count,
        len(raw_tokens),
    ):
        suggestions = None
        if best_entry.get("suggestions"):
            suggestions = best_entry["suggestions"].get(language)
        if not suggestions:
            suggestions = FAQ_SUGGESTIONS_BY_LANGUAGE[language]
        return ChatResponse(
            reply=best_entry["answers"][language],
            suggestions=suggestions,
            link=best_entry.get("link"),
        )
    return None


def normalize_keywords(keywords: list[str]) -> list[str]:
    normalized: list[str] = []
    for keyword in keywords:
        keyword_norm = normalize_text(keyword)
        if keyword_norm:
            normalized.append(keyword_norm)
    return normalized


IMMO_KEYWORDS = normalize_keywords([
    "immobilier",
    "appartement",
    "appartements",
    "maison",
    "maisons",
    "villa",
    "villas",
    "studio",
    "studios",
    "logement",
    "logements",
    "chambre",
    "chambres",
    "duplex",
    "hébergement",
    "hebergement",
    "accommodation",
    "real estate",
    "property",
    "properties",
    "house",
    "home",
    "apartment",
    "apartments",
    "lodging",
    "housing",
    "سكن",
    "سكنات",
    "شقة",
    "شقق",
    "منزل",
    "بيت",
    "فيلا",
    "غرفة",
    "إقامة",
    "اقامة",
    "عقار",
    "عقارات",
])

VEHICULE_KEYWORDS = normalize_keywords([
    "voiture",
    "voitures",
    "vehicule",
    "véhicule",
    "vehicules",
    "moto",
    "motos",
    "scooter",
    "scooters",
    "4x4",
    "auto",
    "berline",
    "suv",
    "car",
    "cars",
    "vehicle",
    "vehicles",
    "rent a car",
    "rental car",
    "motorbike",
    "motorbikes",
    "bike",
    "bikes",
    "سيارة",
    "سيارات",
    "مركبة",
    "مركبات",
    "دراجة",
    "دراجات",
    "استئجار سيارة",
    "تأجير سيارة",
    "كراء سيارة",
])

ACTIVITE_KEYWORDS = normalize_keywords([
    "activité",
    "activite",
    "activités",
    "activites",
    "excursion",
    "excursions",
    "randonnée",
    "randonnee",
    "randonnées",
    "sport",
    "loisir",
    "loisirs",
    "visite",
    "visites",
    "tour",
    "sortie",
    "plage",
    "montagne",
    "activity",
    "activities",
    "trip",
    "hiking",
    "experience",
    "experiences",
    "نشاط",
    "أنشطة",
    "انشطة",
    "رحلة",
    "رحلات",
    "جولة",
    "جولات",
    "مغامرة",
    "تجربة",
    "تجارب",
    "نزهة",
])

BEJAIA_KEYWORDS = normalize_keywords([
    "béjaïa",
    "bejaia",
    "bgayet",
    "بجاية",
])

ALGER_KEYWORDS = normalize_keywords([
    "alger",
    "algers",
    "algiers",
    "el djazair",
    "الجزائر",
    "الجزائر العاصمة",
    "الجزاير",
])

GREETING_KEYWORDS = normalize_keywords([
    "bonjour",
    "salut",
    "hello",
    "bonsoir",
    "hi",
    "salam",
    "السلام",
    "مرحبا",
    "مرحبًا",
    "اهلا",
    "أهلا",
])

BOOKING_KEYWORDS = normalize_keywords([
    "réserver",
    "reserver",
    "réservation",
    "reservation",
    "book",
    "booking",
    "disponible",
    "disponibilité",
    "disponibilite",
    "availability",
    "available",
    "reserve",
    "حجز",
    "حجوزات",
])

PRICE_KEYWORDS = normalize_keywords([
    "prix",
    "tarif",
    "coût",
    "cout",
    "combien",
    "da",
    "dinar",
    "payer",
    "price",
    "cost",
    "how much",
    "fee",
    "fees",
    "سعر",
    "أسعار",
    "اسعار",
    "تكلفة",
    "كم",
    "دج",
])

HOST_KEYWORDS = normalize_keywords([
    "hôte",
    "hote",
    "propriétaire",
    "proprietaire",
    "annonceur",
    "publier",
    "publication",
    "mettre en ligne",
    "devenir hôte",
    "devenir hote",
    "host",
    "owner",
    "listing",
    "publish",
    "list my",
    "mon annonce",
    "mes annonces",
    "espace hote",
    "espace hôte",
    "مضيف",
    "مستضيف",
    "استضافة",
    "نشر",
    "إعلان",
    "اعلان",
])

HELP_KEYWORDS = normalize_keywords([
    "aide",
    "help",
    "assistance",
    "support",
    "info",
    "information",
    "comment ca marche",
    "comment ça marche",
    "how does it work",
    "guide",
    "مساعدة",
    "مساندة",
    "دعم",
    "كيف يعمل",
])

CONTACT_KEYWORDS = normalize_keywords([
    "contact",
    "appeler",
    "téléphone",
    "telephone",
    "joindre",
    "parler",
    "call",
    "phone",
    "reach",
    "email",
    "mail",
    "تواصل",
    "اتصال",
    "هاتف",
])

ACCOUNT_KEYWORDS = normalize_keywords([
    "compte",
    "connexion",
    "inscription",
    "profil",
    "login",
    "connecter",
    "inscrire",
    "account",
    "sign in",
    "sign up",
    "register",
    "profile",
    "تسجيل",
    "حساب",
    "دخول",
    "إنشاء حساب",
    "انشاء حساب",
])

CANCEL_KEYWORDS = normalize_keywords([
    "annuler",
    "annulation",
    "cancel",
    "cancellation",
    "إلغاء",
    "الغاء",
])

THANKS_KEYWORDS = normalize_keywords([
    "merci",
    "thanks",
    "thank you",
    "شكرا",
    "شكرًا",
])


def prepare_text(text: str) -> tuple[str, list[str], set[str]]:
    normalized = normalize_text(text)
    tokens = normalized.split()
    return normalized, tokens, set(tokens)


def keyword_hits(message_norm: str, tokens_set: set[str], keywords: list[str]) -> int:
    hits = 0
    for keyword in keywords:
        if " " in keyword:
            if keyword in message_norm:
                hits += 1
        elif keyword in tokens_set:
            hits += 1
    return hits


def normalize_context(context: Optional[str]) -> Optional[str]:
    if context in {"immobilier", "vehicule", "activite"}:
        return context
    return None


def detect_intent(text: str, context: Optional[str] = None) -> dict:
    """Analyse le message et retourne l'intention détectée."""
    message_norm, _tokens, tokens_set = prepare_text(text)

    immo_hits = keyword_hits(message_norm, tokens_set, IMMO_KEYWORDS)
    vehicule_hits = keyword_hits(message_norm, tokens_set, VEHICULE_KEYWORDS)
    activite_hits = keyword_hits(message_norm, tokens_set, ACTIVITE_KEYWORDS)

    category_scores = {
        "immobilier": immo_hits,
        "vehicule": vehicule_hits,
        "activite": activite_hits,
    }
    positive_categories = [key for key, value in category_scores.items() if value > 0]
    has_multi_category = len(positive_categories) > 1
    category: Optional[str] = None
    if len(positive_categories) == 1:
        category = positive_categories[0]
    elif len(positive_categories) > 1:
        sorted_scores = sorted(category_scores.items(), key=lambda item: item[1], reverse=True)
        if sorted_scores[0][1] >= sorted_scores[1][1] + 1:
            category = sorted_scores[0][0]
            has_multi_category = False

    context_category = normalize_context(context)

    is_greeting = keyword_hits(message_norm, tokens_set, GREETING_KEYWORDS) > 0
    is_booking = keyword_hits(message_norm, tokens_set, BOOKING_KEYWORDS) > 0
    is_price = keyword_hits(message_norm, tokens_set, PRICE_KEYWORDS) > 0
    is_host = keyword_hits(message_norm, tokens_set, HOST_KEYWORDS) > 0
    is_help = keyword_hits(message_norm, tokens_set, HELP_KEYWORDS) > 0
    is_contact = keyword_hits(message_norm, tokens_set, CONTACT_KEYWORDS) > 0
    is_account = keyword_hits(message_norm, tokens_set, ACCOUNT_KEYWORDS) > 0
    is_cancel = keyword_hits(message_norm, tokens_set, CANCEL_KEYWORDS) > 0
    is_thanks = keyword_hits(message_norm, tokens_set, THANKS_KEYWORDS) > 0
    is_bejaia = keyword_hits(message_norm, tokens_set, BEJAIA_KEYWORDS) > 0
    is_alger = keyword_hits(message_norm, tokens_set, ALGER_KEYWORDS) > 0

    return {
        "category": category,
        "context_category": context_category,
        "has_multi_category": has_multi_category,
        "is_immo": immo_hits > 0,
        "is_vehicule": vehicule_hits > 0,
        "is_activite": activite_hits > 0,
        "is_bejaia": is_bejaia,
        "is_alger": is_alger,
        "is_greeting": is_greeting,
        "is_booking": is_booking,
        "is_price": is_price,
        "is_host": is_host,
        "is_help": is_help,
        "is_contact": is_contact,
        "is_account": is_account,
        "is_cancel": is_cancel,
        "is_thanks": is_thanks,
    }


def build_response_fr(intent: dict, _message: str) -> ChatResponse:
    category = intent.get("category")
    context_category = intent.get("context_category")
    has_multi_category = intent.get("has_multi_category", False)
    category_for_action = category
    if category_for_action is None and context_category and (intent["is_price"] or intent["is_booking"]):
        category_for_action = context_category

    has_action_intent = any([
        intent["is_price"],
        intent["is_booking"],
        intent["is_host"],
        intent["is_account"],
        intent["is_help"],
        intent["is_contact"],
        intent["is_cancel"],
    ])

    if intent["is_greeting"] and not category and not has_multi_category and not has_action_intent and not intent["is_thanks"]:
        return ChatResponse(
            reply=(
                "Bonjour ! 👋 Je suis l'assistant TouriGo.\n"
                "Je peux vous aider à trouver un logement, louer un véhicule "
                "ou découvrir des activités locales en Algérie.\n"
                "Qu'est-ce que je peux faire pour vous ?"
            ),
            suggestions=[
                "🏠 Voir l'immobilier",
                "🚗 Louer un véhicule",
                "🌴 Découvrir des activités",
            ],
        )

    if intent["is_thanks"] and not category and not has_multi_category and not has_action_intent:
        return ChatResponse(
            reply="Avec plaisir ! Dites-moi ce que vous cherchez, je suis là pour aider.",
            suggestions=["🏠 Immobilier", "🚗 Véhicules", "🌴 Activités"],
        )

    if has_multi_category:
        return ChatResponse(
            reply=(
                "Vous cherchez plutôt un logement, un véhicule ou une activité ? "
                "Je peux vous orienter vers la bonne catégorie."
            ),
            suggestions=["🏠 Immobilier", "🚗 Véhicules", "🌴 Activités"],
        )

    if intent["is_account"]:
        return ChatResponse(
            reply=(
                "Pour accéder à votre compte, vous pouvez vous connecter ou vous inscrire. "
                "Cela vous permettra de réserver, de sauvegarder vos favoris et de gérer vos annonces."
            ),
            suggestions=["🔑 Se connecter", "📝 S'inscrire"],
            link="/connexion",
        )

    if intent["is_host"]:
        return ChatResponse(
            reply=(
                "Vous souhaitez publier une annonce ? 🎉\n"
                "TouriGo vous permet de devenir hôte facilement et de proposer "
                "votre logement, véhicule ou activité à des milliers d'utilisateurs !"
            ),
            suggestions=["✅ Devenir hôte", "📋 Voir toutes les annonces"],
            link="/devenir-hote",
        )

    if intent["is_cancel"]:
        return ChatResponse(
            reply=(
                "Pour annuler une réservation, ouvrez Mes réservations, "
                "sélectionnez l'annonce concernée puis choisissez Annuler. "
                "Si besoin, notre support peut vous aider."
            ),
            suggestions=["❓ Aide", "📋 Voir les annonces"],
            link="/centre-aide",
        )

    if intent["is_price"]:
        category_label = "annonces"
        link = "/resultats"
        if category_for_action == "immobilier":
            category_label = "logements"
            link = "/immobilier"
        elif category_for_action == "vehicule":
            category_label = "véhicules"
            link = "/vehicules"
        elif category_for_action == "activite":
            category_label = "activités"
            link = "/activites"
        return ChatResponse(
            reply=(
                f"Les prix varient selon les {category_label} et leur emplacement. "
                "Consultez les annonces pour voir les tarifs détaillés de chaque offre. "
                "Aucune commission cachée !"
            ),
            suggestions=[f"🔍 Voir les {category_label}", "📍 Filtrer par ville"],
            link=link,
        )

    if intent["is_booking"]:
        link = "/resultats"
        if category_for_action == "immobilier":
            link = "/immobilier"
        elif category_for_action == "vehicule":
            link = "/vehicules"
        elif category_for_action == "activite":
            link = "/activites"
        return ChatResponse(
            reply=(
                "Pour réserver, trouvez une annonce qui vous convient, "
                "choisissez vos dates et envoyez votre demande à l'hôte. "
                "Vous recevrez une confirmation par notification. 📩"
            ),
            suggestions=["🏠 Chercher un logement", "🚗 Chercher un véhicule", "🌴 Chercher une activité"],
            link=link,
        )

    if intent["is_contact"]:
        return ChatResponse(
            reply=(
                "Vous pouvez contacter directement un hôte via la messagerie intégrée "
                "sur la page de l'annonce. Notre équipe reste aussi disponible pour "
                "toute assistance supplémentaire."
            ),
            suggestions=["📋 Voir les annonces", "❓ Aide"],
        )

    if intent["is_help"]:
        return ChatResponse(
            reply=(
                "TouriGo est une plateforme algérienne pour trouver :\n"
                "🏠 Des logements à louer\n"
                "🚗 Des véhicules à louer\n"
                "🌴 Des activités et excursions locales\n\n"
                "Dites-moi ce que vous cherchez !"
            ),
            suggestions=["🏠 Immobilier", "🚗 Véhicules", "🌴 Activités"],
        )

    if category == "immobilier":
        city_info = ""
        if intent["is_bejaia"]:
            city_info = "à Béjaïa "
        elif intent["is_alger"]:
            city_info = "à Alger "

        return ChatResponse(
            reply=(
                f"Excellente idée ! 🏠 Nous avons des logements {city_info}disponibles. "
                "Appartements, maisons, villas... découvrez toutes nos offres immobilières "
                "et choisissez celle qui vous convient."
            ),
            suggestions=["🔍 Rechercher un logement", "📍 Filtrer par ville", "💰 Voir les prix"],
            link="/immobilier",
        )

    if category == "vehicule":
        city_info = ""
        if intent["is_bejaia"]:
            city_info = "à Béjaïa "
        elif intent["is_alger"]:
            city_info = "à Alger "

        return ChatResponse(
            reply=(
                f"Parfait ! 🚗 Trouvez le véhicule idéal {city_info}parmi nos annonces. "
                "Voitures, 4x4, motos... Comparez les offres et réservez directement."
            ),
            suggestions=["🔍 Chercher un véhicule", "📍 Filtrer par ville", "💰 Voir les tarifs"],
            link="/vehicules",
        )

    if category == "activite":
        city_info = ""
        if intent["is_bejaia"]:
            city_info = "à Béjaïa "
        elif intent["is_alger"]:
            city_info = "à Alger "

        return ChatResponse(
            reply=(
                f"Super ! 🌴 Découvrez des activités et excursions {city_info}pour des souvenirs inoubliables. "
                "Randonnées, sports nautiques, visites guidées... il y en a pour tous les goûts !"
            ),
            suggestions=["🔍 Voir les activités", "📍 Activités à Béjaïa", "📍 Activités à Alger"],
            link="/activites",
        )

    if intent["is_bejaia"]:
        return ChatResponse(
            reply=(
                "Béjaïa est une magnifique destination ! ⛰️🌊 "
                "Que cherchez-vous pour ce séjour ?"
            ),
            suggestions=["🏠 Logement à Béjaïa", "🚗 Véhicule à Béjaïa", "🌴 Activités à Béjaïa"],
            link="/resultats?destination=bejaia",
        )

    if intent["is_alger"]:
        return ChatResponse(
            reply=(
                "Alger, la Blanche ! 🏙️ "
                "Que puis-je trouver pour vous dans la capitale ?"
            ),
            suggestions=["🏠 Logement à Alger", "🚗 Véhicule à Alger", "🌴 Activités à Alger"],
            link="/resultats?destination=alger",
        )

    return ChatResponse(
        reply=(
            "Je ne suis pas sûr de comprendre votre demande 🤔 "
            "Mais je peux vous aider à trouver un logement, un véhicule ou une activité ! "
            "Que cherchez-vous ?"
        ),
        suggestions=[
            "🏠 Voir l'immobilier",
            "🚗 Louer un véhicule",
            "🌴 Découvrir des activités",
            "❓ Aide",
        ],
    )


def build_response_ar(intent: dict, _message: str) -> ChatResponse:
    category = intent.get("category")
    context_category = intent.get("context_category")
    has_multi_category = intent.get("has_multi_category", False)
    category_for_action = category
    if category_for_action is None and context_category and (intent["is_price"] or intent["is_booking"]):
        category_for_action = context_category

    has_action_intent = any([
        intent["is_price"],
        intent["is_booking"],
        intent["is_host"],
        intent["is_account"],
        intent["is_help"],
        intent["is_contact"],
        intent["is_cancel"],
    ])

    if intent["is_greeting"] and not category and not has_multi_category and not has_action_intent and not intent["is_thanks"]:
        return ChatResponse(
            reply=(
                "مرحبًا! 👋 أنا مساعد TouriGo.\n"
                "يمكنني مساعدتك في العثور على سكن، استئجار مركبة "
                "أو اكتشاف أنشطة محلية في الجزائر.\n"
                "كيف يمكنني مساعدتك؟"
            ),
            suggestions=[
                "🏠 عرض العقارات",
                "🚗 استئجار مركبة",
                "🌴 اكتشاف الأنشطة",
            ],
        )

    if intent["is_thanks"] and not category and not has_multi_category and not has_action_intent:
        return ChatResponse(
            reply="على الرحب والسعة! أخبرني ماذا تبحث عنه وسأساعدك.",
            suggestions=["🏠 العقارات", "🚗 المركبات", "🌴 الأنشطة"],
        )

    if has_multi_category:
        return ChatResponse(
            reply="هل تبحث عن سكن أم مركبة أم نشاط؟ يمكنني توجيهك للفئة المناسبة.",
            suggestions=["🏠 العقارات", "🚗 المركبات", "🌴 الأنشطة"],
        )

    if intent["is_account"]:
        return ChatResponse(
            reply=(
                "للوصول إلى حسابك يمكنك تسجيل الدخول أو إنشاء حساب جديد. "
                "هذا يتيح لك الحجز، حفظ المفضلة وإدارة إعلاناتك."
            ),
            suggestions=["🔑 تسجيل الدخول", "📝 إنشاء حساب"],
            link="/connexion",
        )

    if intent["is_host"]:
        return ChatResponse(
            reply=(
                "هل تريد نشر إعلان؟ 🎉\n"
                "مع TouriGo يمكنك أن تصبح مضيفًا بسهولة وتعرض "
                "سكنك أو مركبتك أو نشاطك لآلاف المستخدمين!"
            ),
            suggestions=["✅ أصبح مضيفًا", "📋 عرض كل الإعلانات"],
            link="/devenir-hote",
        )

    if intent["is_cancel"]:
        return ChatResponse(
            reply=(
                "لإلغاء الحجز، افتح حجوزاتي، اختر الإعلان ثم اضغط إلغاء. "
                "إذا احتجت مساعدة إضافية يمكن لفريق الدعم مساعدتك."
            ),
            suggestions=["❓ مساعدة", "📋 عرض الإعلانات"],
            link="/centre-aide",
        )

    if intent["is_price"]:
        category_label = "الإعلانات"
        suggestion = "🔍 عرض الإعلانات"
        link = "/resultats"
        if category_for_action == "immobilier":
            category_label = "العقارات"
            suggestion = "🔍 عرض العقارات"
            link = "/immobilier"
        elif category_for_action == "vehicule":
            category_label = "المركبات"
            suggestion = "🔍 عرض المركبات"
            link = "/vehicules"
        elif category_for_action == "activite":
            category_label = "الأنشطة"
            suggestion = "🔍 عرض الأنشطة"
            link = "/activites"
        return ChatResponse(
            reply=(
                f"تختلف الأسعار حسب {category_label} والموقع. "
                "تصفح الإعلانات للاطلاع على السعر التفصيلي لكل عرض. "
                "بدون عمولات مخفية!"
            ),
            suggestions=[suggestion, "📍 التصفية حسب المدينة"],
            link=link,
        )

    if intent["is_booking"]:
        link = "/resultats"
        if category_for_action == "immobilier":
            link = "/immobilier"
        elif category_for_action == "vehicule":
            link = "/vehicules"
        elif category_for_action == "activite":
            link = "/activites"
        return ChatResponse(
            reply=(
                "لإتمام الحجز، اختر الإعلان المناسب لك، "
                "حدد التواريخ ثم أرسل طلبك إلى المضيف. "
                "ستصلك رسالة تأكيد عبر الإشعارات. 📩"
            ),
            suggestions=["🏠 البحث عن سكن", "🚗 البحث عن مركبة", "🌴 البحث عن نشاط"],
            link=link,
        )

    if intent["is_contact"]:
        return ChatResponse(
            reply=(
                "يمكنك التواصل مباشرة مع المضيف عبر المراسلة داخل صفحة الإعلان. "
                "وفريقنا متاح أيضًا لأي مساعدة إضافية."
            ),
            suggestions=["📋 عرض الإعلانات", "❓ مساعدة"],
        )

    if intent["is_help"]:
        return ChatResponse(
            reply=(
                "TouriGo منصة جزائرية تساعدك على العثور على:\n"
                "🏠 سكن للإيجار\n"
                "🚗 مركبات للإيجار\n"
                "🌴 أنشطة ورحلات محلية\n\n"
                "أخبرني ماذا تبحث عنه!"
            ),
            suggestions=["🏠 العقارات", "🚗 المركبات", "🌴 الأنشطة"],
        )

    if category == "immobilier":
        city_info = ""
        if intent["is_bejaia"]:
            city_info = "في بجاية "
        elif intent["is_alger"]:
            city_info = "في الجزائر العاصمة "

        return ChatResponse(
            reply=(
                f"فكرة ممتازة! 🏠 لدينا مساكن {city_info}متاحة. "
                "شقق، منازل، فيلات... تصفح عروضنا العقارية واختر ما يناسبك."
            ),
            suggestions=["🔍 البحث عن سكن", "📍 التصفية حسب المدينة", "💰 عرض الأسعار"],
            link="/immobilier",
        )

    if category == "vehicule":
        city_info = ""
        if intent["is_bejaia"]:
            city_info = "في بجاية "
        elif intent["is_alger"]:
            city_info = "في الجزائر العاصمة "

        return ChatResponse(
            reply=(
                f"ممتاز! 🚗 ابحث عن المركبة المناسبة {city_info}ضمن إعلاناتنا. "
                "سيارات، 4x4، دراجات... قارن العروض واحجز مباشرة."
            ),
            suggestions=["🔍 البحث عن مركبة", "📍 التصفية حسب المدينة", "💰 عرض الأسعار"],
            link="/vehicules",
        )

    if category == "activite":
        city_info = ""
        if intent["is_bejaia"]:
            city_info = "في بجاية "
        elif intent["is_alger"]:
            city_info = "في الجزائر العاصمة "

        return ChatResponse(
            reply=(
                f"رائع! 🌴 اكتشف أنشطة ورحلات {city_info}لتجربة لا تُنسى. "
                "جولات، أنشطة بحرية، زيارات موجهة... لكل الأذواق."
            ),
            suggestions=["🔍 عرض الأنشطة", "📍 أنشطة في بجاية", "📍 أنشطة في الجزائر"],
            link="/activites",
        )

    if intent["is_bejaia"]:
        return ChatResponse(
            reply="بجاية وجهة رائعة! ⛰️🌊 ماذا تبحث له خلال هذا السفر؟",
            suggestions=["🏠 سكن في بجاية", "🚗 مركبة في بجاية", "🌴 أنشطة في بجاية"],
            link="/resultats?destination=bejaia",
        )

    if intent["is_alger"]:
        return ChatResponse(
            reply="الجزائر العاصمة! 🏙️ ماذا تريد أن تجد هناك؟",
            suggestions=["🏠 سكن في الجزائر", "🚗 مركبة في الجزائر", "🌴 أنشطة في الجزائر"],
            link="/resultats?destination=alger",
        )

    return ChatResponse(
        reply=(
            "لم أفهم طلبك بالكامل 🤔 "
            "لكن يمكنني مساعدتك في العثور على سكن أو مركبة أو نشاط. "
            "ماذا تبحث عنه؟"
        ),
        suggestions=[
            "🏠 عرض العقارات",
            "🚗 استئجار مركبة",
            "🌴 اكتشاف الأنشطة",
            "❓ مساعدة",
        ],
    )


def build_response(intent: dict, message: str, language: Language = "fr") -> ChatResponse:
    if language == "ar":
        return build_response_ar(intent, message)
    return build_response_fr(intent, message)


@router.post("/message", response_model=ChatResponse)
async def chat(payload: ChatMessage):
    """Endpoint principal du chatbot TouriGo."""
    faq_response = match_faq(payload.message, payload.language)
    if faq_response is not None:
        return faq_response
    intent = detect_intent(payload.message, payload.context)
    return build_response(intent, payload.message, payload.language)


@router.get("/welcome", response_model=ChatResponse)
async def welcome(language: Language = "fr"):
    """Message de bienvenue initial du chatbot."""
    if language == "ar":
        return ChatResponse(
            reply=(
                "مرحبًا! 👋 أنا مساعدك في TouriGo.\n"
                "أنا هنا لمساعدتك في العثور على السكن المثالي، "
                "استئجار مركبة أو اكتشاف الأنشطة المحلية في الجزائر.\n"
                "كيف يمكنني مساعدتك؟"
            ),
            suggestions=[
                "🏠 عرض العقارات",
                "🚗 استئجار مركبة",
                "🌴 اكتشاف الأنشطة",
            ],
        )

    return ChatResponse(
        reply=(
            "Bonjour ! 👋 Je suis votre assistant TouriGo.\n"
            "Je suis là pour vous aider à trouver le logement idéal, "
            "louer un véhicule ou découvrir des activités locales en Algérie.\n"
            "Comment puis-je vous aider ?"
        ),
        suggestions=[
            "🏠 Voir l'immobilier",
            "🚗 Louer un véhicule",
            "🌴 Découvrir des activités",
        ],
    )
