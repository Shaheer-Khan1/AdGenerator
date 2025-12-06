"""
Test script to see how the system processes a French collagen transcription
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Your French transcription
TRANSCRIPTION = """J'ai testé ce nouveau type de collagène pendant 80 jours parce que tout le monde en parler. Honnêtement, je pensais que c'était encore une arnac de plus. Mais au bout de 6 semaines, j'étais surprise. J'ai entendu que ce nouveau type de collagène était révolutionnaire, mais aussi que c'était juste du marketing intelligent. Alors j'ai mené mon propre test sur 80 jours. J'ai d'est-il été 300 euros en collagène classique avant de découvrir qu'il existait un nouveau type totalement différent. Personne ne m'avait parlé de cette différence cruciale. Maintenant je comprends pourquoi rien ne fonctionnais avant. Pourquoi ce nouveau type de collagène fétil autant parler sur les réseaux? Est-ce vraiment différent du collagène normal ou juste un coup de marketing? J'ai décidé de creuser pendant 3 mois. Les résultats sont vraiment surprenants. Avez-vous déjà entendu parler de ce nouveau type de collagène? La différence avec le collagène classique, une molécule 40 fois plus petite. J'ai testé les deux pendant 90 jours pour voir si ça change vraiment quelque chose. J'ai mené le test avec cette nouvelle formulae dont tout le monde parle. Pour pendant 80 jours. La différence est tellement visible que mes amis me demandent ce que j'ai changé. Le collagène en théorie ça devrait marcher. Après 25 ans on perd 1% par an. Ça explique les rites, les articulations qui craquent, les cheveux plus fin. J'ai essayé 5 marques différentes. De la pharmacie, de la drogue, à ma zone, résultat, rien, 0 changement. Et puis j'ai compris pourquoi. La plupart des pours de l'on des molécules trop grosses. Moi de la moitié arrive dans votre sang. C'est comme faire passer un ballon de foot à travers un grieage. Sans compter qu'ils leur mangent généralement des co-facteurs cruciaux comme la vitamine C, qui aide votre corps à absorber plus rapidement ce qui passe. J'avais dépensé des centaines de euros pour rien. Du coup j'ai fait mes petites recherches parce que si autant de célébrités et de médecins donnent leur aval c'est qu'il y a forcément un truc. C'est là que je suis tombé sur Glott-25. Le collagène le plus vendu en Europe. Ma première réaction, encore du marketing. Mais j'ai découvert qu'ils utilisent un procès d'exclusif. Des pépites ultra petit du micro collagène qui passe vraiment la barrière intestinal. Et surtout, pour leur collagène plus, ils ajoutent du zinc de la biotine et de la vitamine C. Pas pour faire jolie. Ces ingrédients boostent la production naturelle de collagène et à meilleure l'absorption. Plus de 20 000 à vies 5 étoiles. Ça semble insuppet. Le prix était plus élevée, mais je me suis dit, si ça marche vraiment, c'est moins cher que le continue à acheter des trucs inutiles. J'ai commandé testes sérieux, 90 jours, tous les jours. Premier point, c'est vraiment sangou. Je le mets dans mon café, je ne sens rien. Finis l'odeur de poisson du collagène marin. Semen 1 à 3, rien de visible. Je commence à douter. Semen 4 et 5, mais angle, plus résistant, il ne casse plus. Semen 6 et 7, ma peau, plus luminosa, t'as un plus uniforme. Semen 8 et au-delà, je n'en revenais pas. Les réduits autour de mes yeux, visiblement atténué. Ma peau était plus ferme au toucher. Enfin, et mes cheveux, j'ai eu du mal à y croire. Mais ils étaient clairement plus épais. Le plus fou, mais je nous qui craquait à chaque mouvement depuis des années, avait presque arrêté. Je pouvais enfameter les escaliers sans ce bruit gênant. Au bout de 80 jours, j'ai aux écompareés mes photos. Mon cœur bâté un peu plus fort. Et là, la différence était belle et bien là. Pas de miracle au-delà, mais quelque chose de réelle. De naturel, de vrai, pour la première fois de ma vie, un collagène me donner des résultats concret. J'étais ému. Sous l'agé, enfin, quelque chose qui fonctionnait vraiment. Maintenant, je comprends pourquoi tant de gens en parle, les avis positifs reflettes visiblement une vraie expérience. Est-ce que ça vaut le coup ? Oui, carrément. Mais avant, je dépensez 25 à 30 euros par mois en collagène qui ne faisait rien. 360 euros par an, je t'ai avec l'autantifive au moins sa marche. Donc, au final, je gaspie moins. Je ne dis pas que c'est magique. Il faut être régulier. Les 1er résultats, 3 à 4 semaines minimum. Mais la différence, c'est cette taille de peptide. Si les molécules sont trop grosses, peu importent la quantité, ça ne sert à rien. Et puis, avec les co-facteurs comme le zinc, la vitamine et la biotine, l'absorption ne pourrait pas être plus efficace. Moi, je continue. Maintenant que j'ai vu des résultats, pas question de revenir en arrière. Maintenant, je comprends pourquoi tant de gens en parle. Les avis positifs reflèrent de visiblement une vraie expérience. Beaucoup m'ont demandé ou trouvé la meilleure offre. J'ai négocié une offre exclusive réservée à nos lectrices, disponible pour une durée limitée avec la garantie du meilleur prix."""

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("\n❌ ERROR: GEMINI_API_KEY not found in .env file!")
    print("   Please add it to your .env file")
    sys.exit(1)

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_keyword_detection():
    """Test 1: Detect French keywords"""
    print_section("TEST 1: FRENCH KEYWORD DETECTION")
    
    french_to_english = {
        'collagène': 'collagen supplement skin',
        'peau': 'skin care face',
        'rides': 'wrinkles anti aging',
        'cheveux': 'hair care beauty',
        'ongles': 'nails manicure',
        'café': 'coffee drink',
        'cellulite': 'cellulite treatment',
        'articulations': 'joints health',
        'ménopause': 'menopause health',
        'visage': 'face beauty',
        'crème': 'cream skincare',
        'vitamine': 'vitamin supplement',
        'supplément': 'supplement health'
    }
    
    topics_detected = []
    script_lower = TRANSCRIPTION.lower()
    
    print("\nScanning transcription for French keywords...\n")
    
    for french, english in french_to_english.items():
        if french in script_lower:
            count = script_lower.count(french)
            topics_detected.append(english)
            print(f"✓ Found '{french}' ({count} times) → '{english}'")
    
    print(f"\n📊 DETECTED TOPICS: {', '.join(set(topics_detected[:5]))}")
    
    return topics_detected

def test_fallback_keywords():
    """Test 2: Fallback keyword extraction"""
    print_section("TEST 2: FALLBACK KEYWORD EXTRACTION")
    
    words = TRANSCRIPTION.lower().split()
    
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
        'by', 'from', 'is', 'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'can', 'may', 'might',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
        'your', 'our', 'their', 'my', 'his', 'her', 'its', 'what', 'which', 'who',
        'when', 'where', 'why', 'how', 'all', 'each', 'every', 'some', 'many', 'much',
        'more', 'most', 'other', 'such', 'only', 'just', 'very', 'too', 'also',
        'que', 'les', 'des', 'une', 'dans', 'pour', 'avec', 'est', 'pas', 'sur'
    }
    
    visual_keywords = []
    for word in words:
        clean_word = word.strip('.,!?;:')
        if len(clean_word) > 4 and clean_word not in stop_words:
            visual_keywords.append(clean_word)
    
    print(f"\nExtracted {len(visual_keywords)} meaningful keywords (length > 4 chars)")
    print(f"\nFirst 15 keywords: {', '.join(visual_keywords[:15])}")
    print(f"\n📊 FALLBACK QUERY (first 10): {' '.join(visual_keywords[:10])}")
    
    return visual_keywords[:10]

def test_gemini_search_query(detected_topics):
    """Test 3: Generate search query with Gemini"""
    print_section("TEST 3: GEMINI SEARCH QUERY GENERATION")
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        detected_context = ""
        if detected_topics:
            detected_context = f"\n\nDetected topics (use these for context): {', '.join(set(detected_topics[:5]))}"
        
        script_text = TRANSCRIPTION[:500]
        
        prompt = f"""You are a video search specialist. Analyze this transcription (which may be in any language) and create a HIGHLY SPECIFIC search query IN ENGLISH for finding relevant stock videos on Pexels.

Transcription: "{script_text}"{detected_context}

IMPORTANT: 
- The transcription may be in French, English, or other languages
- You MUST respond with the search query in ENGLISH only
- First understand what the transcription is about, then translate concepts to English search terms

Your task:
1. Identify ALL visual elements being described (people, products, actions, settings, emotions)
2. Translate key concepts to ENGLISH visual terms
3. Think about what would look good on camera (close-ups, activities, emotions, results)
4. Use CONCRETE, VISUAL terms (not abstract concepts)
5. Be DETAILED and SPECIFIC - include multiple visual elements
6. Include WHO is in the video (woman, person, hands, face, body parts, etc.)
7. Include WHAT action is happening (applying, taking, drinking, showing, comparing)
8. Include visual RESULTS or emotions (glowing, smooth, shiny, happy, confident)
9. Focus on MULTIPLE aspects to get more relevant results

Good examples (all in English, detailed):
- "beautiful woman applying collagen cream on face smooth glowing skin closeup"
- "woman taking supplement pills vitamin bottle health wellness routine"
- "close up mature woman face before after wrinkles anti aging treatment"
- "hands massaging face skincare routine cream application beauty"
- "woman brushing long shiny healthy hair beauty care routine"
- "before after skin comparison wrinkles aging smooth radiant results"
- "woman drinking coffee morning routine glowing skin beauty lifestyle"

Bad examples:
- "beauty wellness" (too vague, too short)
- "good product" (not visual, not specific)
- "woman face" (too generic, needs more detail)
- "santé beauté" (not in English - must translate to English)

Context clues for translation:
- If about "collagène" → "woman taking collagen supplement powder drink skin health"
- If about "café" → "woman drinking coffee morning routine beauty lifestyle"
- If about "cheveux" → "woman brushing styling long shiny hair beauty care"
- If about "peau" → "woman face skin care routine cream application closeup"
- If about "rides" → "woman face before after wrinkles anti aging treatment results"
- If about "supplément/vitamine" → "woman taking supplement vitamin pills health wellness"

Now create a DETAILED search query (8-12 words) IN ENGLISH that focuses on WHAT THE CAMERA WOULD SEE.
Include WHO, WHAT action, and VISUAL details:

Search query:"""

        print("\nSending to Gemini AI...\n")
        print(f"📝 Transcription length: {len(TRANSCRIPTION)} chars")
        print(f"📝 Detected context: {detected_context.strip()}")
        print(f"\n⏳ Waiting for Gemini response...")
        
        response = model.generate_content(prompt)
        search_query = response.text.strip().strip('"\'')
        
        print(f"\n✅ GENERATED SEARCH QUERY:")
        print(f"   '{search_query}'")
        print(f"\n📊 Query length: {len(search_query.split())} words")
        
        return search_query
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None

def test_folder_selection():
    """Test 4: Folder selection"""
    print_section("TEST 4: FOLDER SELECTION")
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        available_folders = [
            "Cellulite",
            "Glow Coffee", 
            "Hair",
            "Joints",
            "Menopause",
            "Nails",
            "Others",
            "Product",
            "Wrinkles"
        ]
        
        prompt = f"""Analyze this transcription and choose ALL RELEVANT folders for video footage (not just one).

Transcription: "{TRANSCRIPTION[:500]}"

Available folders:
{chr(10).join(f'- {folder}' for folder in available_folders)}

Rules:
1. Choose ALL folders that match the topic (can be multiple)
2. If it's about a product, include "Product"
3. If it mentions specific benefits (skin, hair, joints), include those folders too
4. Respond with folder names separated by commas

Folders:"""
        
        print("\nAsking Gemini to select ALL relevant folders...\n")
        
        response = model.generate_content(prompt)
        folders_text = response.text.strip()
        
        # Parse comma-separated folders
        suggested_folders = []
        for folder in folders_text.split(','):
            folder = folder.strip()
            # Validate
            for valid_folder in available_folders:
                if valid_folder.lower() in folder.lower() or folder.lower() in valid_folder.lower():
                    if valid_folder not in suggested_folders:
                        suggested_folders.append(valid_folder)
                    break
        
        if not suggested_folders:
            suggested_folders = ["Others"]
        
        print(f"✅ SELECTED FOLDERS: {', '.join(suggested_folders)}")
        print(f"📊 Total folders selected: {len(suggested_folders)}")
        
        return suggested_folders
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return ["Product"]

def test_video_generation_simulation(search_query, selected_folders):
    """Test 5: Simulate video generation"""
    print_section("TEST 5: VIDEO GENERATION SIMULATION")
    
    print(f"\n📝 Search Query: '{search_query}'")
    print(f"📁 Selected Folders: {', '.join(selected_folders)}")
    
    # Simulate what Pexels would return
    print(f"\n🔍 Searching Pexels for: '{search_query}'")
    print("\n📊 Expected Pexels Results:")
    
    pexels_predictions = {
        "collagen": ["woman taking supplement pills", "collagen powder jar", "woman mixing supplement drink"],
        "supplement": ["vitamin bottles", "woman taking pills", "supplement powder"],
        "product": ["beauty product bottles", "skincare packaging", "supplement container"],
        "skin": ["woman face closeup glowing", "smooth skin texture", "skincare routine"],
        "glowing": ["radiant skin woman", "glowing complexion", "healthy skin closeup"],
        "transformation": ["before after comparison", "woman looking at mirror", "skin improvement"],
        "routine": ["morning skincare routine", "daily supplement taking", "woman wellness routine"],
        "bottle": ["product bottle white background", "supplement jar label", "beauty product packaging"]
    }
    
    keywords = search_query.lower().split()
    predicted_videos = []
    
    for keyword, videos in pexels_predictions.items():
        if keyword in search_query.lower():
            predicted_videos.extend(videos)
    
    if not predicted_videos:
        predicted_videos = ["woman beauty wellness", "skincare routine", "supplement taking"]
    
    for i, video in enumerate(predicted_videos[:5], 1):
        print(f"  {i}. {video}")
    
    # Check if Product folder visuals would be included
    print(f"\n✅ Product-related visuals expected:")
    product_keywords = ["product", "bottle", "supplement", "collagen", "jar", "packaging"]
    has_product_visuals = any(kw in search_query.lower() for kw in product_keywords)
    
    if has_product_visuals:
        print(f"   ✓ YES - Query includes product terms: {[kw for kw in product_keywords if kw in search_query.lower()]}")
    else:
        print(f"   ✗ NO - Query doesn't emphasize products")
    
    # Folder context
    if "Product" in selected_folders:
        print(f"\n✅ Product folder was selected:")
        print(f"   This should help Gemini include product visuals in the query")
    
    return predicted_videos

def main():
    """Run all tests"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "TRANSCRIPTION TEST SUITE" + " "*34 + "║")
    print("╚" + "="*78 + "╝")
    
    print("\n📄 TRANSCRIPTION PREVIEW:")
    print(f"   {TRANSCRIPTION[:150]}...")
    print(f"\n📊 Total length: {len(TRANSCRIPTION)} characters")
    print(f"📊 Word count: {len(TRANSCRIPTION.split())} words")
    
    # Test 1: Keyword detection
    detected_topics = test_keyword_detection()
    
    # Test 2: Fallback keywords
    fallback_keywords = test_fallback_keywords()
    
    # Test 3: Gemini search query
    search_query = test_gemini_search_query(detected_topics)
    
    # Test 4: Folder selection (ALL relevant folders)
    folders = test_folder_selection()
    
    # Test 5: Video generation simulation
    predicted_videos = test_video_generation_simulation(search_query, folders)
    
    # Summary
    print_section("SUMMARY")
    print(f"\n1. Detected Topics: {', '.join(set(detected_topics[:5]))}")
    print(f"\n2. Fallback Keywords: {' '.join(fallback_keywords)}")
    print(f"\n3. Gemini Search Query: '{search_query}'")
    print(f"\n4. Selected Folders: {', '.join(folders)}")
    print(f"\n5. Predicted Videos: {len(predicted_videos)} videos")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED")
    print("="*80 + "\n")
    
    # Analysis
    print_section("ANALYSIS")
    print("\n🎯 Query Quality Check:")
    
    # Check query length
    query_length = len(search_query.split())
    if query_length >= 10:
        print(f"  ✅ Query length: {query_length} words (good detail)")
    else:
        print(f"  ⚠️  Query length: {query_length} words (could be more detailed)")
    
    # Check product terms
    product_terms = ["product", "bottle", "supplement", "collagen", "jar", "packaging", "container"]
    found_product_terms = [term for term in product_terms if term in search_query.lower()]
    
    if "Product" in folders:
        if found_product_terms:
            print(f"  ✅ Product folder selected AND query includes product terms: {found_product_terms}")
        else:
            print(f"  ⚠️  Product folder selected BUT query lacks product terms")
            print(f"     Suggestion: Add words like 'bottle', 'packaging', 'supplement jar'")
    
    # Check storytelling
    story_elements = ["transformation", "before after", "journey", "routine", "results", "surprise"]
    found_story = [elem for elem in story_elements if elem in search_query.lower()]
    
    if found_story:
        print(f"  ✅ Story elements included: {found_story}")
    else:
        print(f"  ⚠️  Missing story elements (transformation, journey, results)")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()

