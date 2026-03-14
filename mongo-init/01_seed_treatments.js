// ─────────────────────────────────────────────────────────────────────────────
// mongo-init/01_seed_treatments.js
// Runs automatically once when the MongoDB container starts for the first time.
// Seeds the treatments collection with disease data for all 4 classes.
// ─────────────────────────────────────────────────────────────────────────────

db = db.getSiblingDB('CropGuard');

// Only seed if the collection is empty (idempotent)
if (db.treatments.countDocuments() === 0) {
  db.treatments.insertMany([
    {
      disease: "Downy mildew",
      description: "Caused by the oomycete Pseudoperonospora cubensis. Favoured by cool, moist conditions and high humidity. One of the most economically important diseases of cucurbits worldwide.",
      severity: "High",
      symptoms: [
        "Yellow angular spots on upper leaf surface bounded by leaf veins",
        "Grey to purple sporulation on lower leaf surface",
        "Leaves curl downward and eventually turn brown and die",
        "Rapid spread under humid conditions"
      ],
      treatments: [
        "Apply fungicides containing chlorothalonil, mancozeb, or copper-based compounds",
        "Use systemic fungicides such as metalaxyl or cymoxanil for established infections",
        "Remove and destroy heavily infected leaves immediately",
        "Ensure adequate plant spacing for air circulation",
        "Avoid overhead irrigation; use drip irrigation instead"
      ],
      prevention: [
        "Plant resistant or tolerant varieties where available",
        "Rotate crops — avoid planting cucurbits in the same field for at least 2 years",
        "Apply preventative fungicide sprays during high-risk periods",
        "Monitor plants regularly for early symptoms",
        "Maintain field sanitation by removing crop debris after harvest"
      ]
    },
    {
      disease: "Healthy",
      description: "No disease detected. The leaf appears healthy and vigorous. Continue standard crop management practices.",
      severity: "None",
      symptoms: [],
      treatments: [
        "Continue regular watering and fertilisation schedule",
        "Monitor plants weekly for any early signs of disease or pest activity",
        "Maintain balanced soil nutrition — excess nitrogen can increase disease susceptibility"
      ],
      prevention: [
        "Maintain good field hygiene and remove weeds that may harbour pests",
        "Ensure adequate spacing between plants for airflow",
        "Use drip irrigation to keep foliage dry",
        "Rotate crops seasonally to prevent soil-borne disease buildup",
        "Scout regularly and act early if symptoms appear"
      ]
    },
    {
      disease: "Leaf curl disease",
      description: "Caused by Cucumber Leaf Curl Virus (CuLCV) transmitted by whiteflies (Bemisia tabaci). Spread is rapid in warm, dry conditions. Can cause severe yield loss if not managed early.",
      severity: "High",
      symptoms: [
        "Upward or downward curling and crinkling of leaves",
        "Yellowing and mosaic-like mottling of leaf tissue",
        "Stunted plant growth and reduced internodal distance",
        "Small, deformed fruits with reduced marketability",
        "Presence of whiteflies on underside of leaves"
      ],
      treatments: [
        "Remove and destroy infected plants immediately to prevent virus spread",
        "Apply insecticides (imidacloprid, thiamethoxam) to control whitefly vectors",
        "Use yellow sticky traps to monitor and reduce whitefly populations",
        "There is no cure once plants are infected — focus on vector control",
        "Apply neem-based sprays as an organic whitefly deterrent"
      ],
      prevention: [
        "Use virus-free certified seeds and seedlings",
        "Install insect-proof nets or row covers at planting",
        "Plant early in the season before whitefly populations peak",
        "Introduce natural predators such as Encarsia formosa for biological control",
        "Avoid planting near heavily infested fields or other cucurbit crops"
      ]
    },
    {
      disease: "Mosaic virus",
      description: "Caused by Cucumber Mosaic Virus (CMV) or Watermelon Mosaic Virus (WMV), transmitted by aphids (Aphis gossypii, Myzus persicae). Reduces fruit quality and marketability significantly.",
      severity: "Medium",
      symptoms: [
        "Light and dark green mosaic or mottling pattern on leaves",
        "Leaf distortion, puckering, and blistering",
        "Stunted shoot growth and shortened internodes",
        "Fruits show yellow streaks, bumps, and irregular shape",
        "Presence of aphid colonies on young shoots and leaf undersides"
      ],
      treatments: [
        "Remove and destroy visibly infected plants to reduce inoculum source",
        "Apply insecticides (pyrethroids, neonicotinoids) to control aphid vectors",
        "Use reflective silver mulch to repel aphids from plants",
        "Spray insecticidal soap or neem oil for organic aphid management",
        "There is no chemical cure for the virus — management focuses on vectors"
      ],
      prevention: [
        "Use certified virus-free planting material",
        "Control weeds around the crop that may serve as virus reservoirs",
        "Avoid working in the crop when plants are wet to reduce mechanical spread",
        "Introduce beneficial insects such as ladybirds and parasitic wasps",
        "Rotate crops and remove all plant debris after harvest"
      ]
    }
  ]);

  print('[Seed] Treatments collection seeded successfully with 4 disease records.');
} else {
  print('[Seed] Treatments collection already populated — skipping seed.');
}
