# The label space

Every species this app can name, generated from `data/taxonomy.seed.json`
by `python scripts/species_list.py`. Do not edit it by hand.

**247 species · 135 lethal lookalike pairs.**

It holds all 200 of the most-recorded British macrofungi (`python scripts/frdbi_gap.py --top 200`) plus the dangerous species each of those is confused with.

> **None of this has been reviewed by a mycologist.** Toxicity, lookalike
> relationships and diagnostic characters are compiled from standard
> references and are unverified. `/health` reports
> `taxonomy_reviewed: false`. See `REVIEW.md`.

> **No entry here says anything is safe to eat.** The app has no such
> category. *Not assessed as safe* is the best case, and it means exactly
> what it says.

## Can kill — `DEADLY` (11)

Eating this can be fatal.

| Species | Also known as | Confused with |
| --- | --- | --- |
| ***Amanita phalloides*** | Death Cap | *Agaricus campestris*, *Agaricus arvensis*, *Russula cyanoxantha*, *Macrolepiota procera* (+1) |
| ***Amanita virosa*** | Destroying Angel | *Agaricus arvensis*, *Agaricus campestris*, *Lycoperdon perlatum*, *Calocybe gambosa* |
| ***Clitocybe dealbata*** | Ivory Funnel | *Marasmius oreades*, *Calocybe gambosa* |
| ***Clitocybe rivulosa*** | Fool's Funnel, Ivory Funnel | *Marasmius oreades*, *Calocybe gambosa*, *Clitopilus prunulus* |
| ***Cortinarius orellanus*** | Fool's Webcap | ***Cortinarius rubellus***, *Cantharellus cibarius*, *Lepista nuda* |
| ***Cortinarius rubellus*** | Deadly Webcap | *Cantharellus cibarius*, *Lactarius deliciosus*, *Armillaria mellea* |
| ***Galerina marginata*** | Funeral Bell | *Kuehneromyces mutabilis*, *Armillaria mellea*, *Hypholoma fasciculare*, *Pholiota squarrosa* |
| ***Gyromitra esculenta*** | False Morel, Turban Fungus | *Morchella esculenta* |
| ***Inocybe erubescens*** | Deadly Fibrecap | *Calocybe gambosa*, *Agaricus campestris* |
| ***Lepiota brunneoincarnata*** | Deadly Dapperling | *Marasmius oreades*, *Agaricus campestris*, *Macrolepiota procera* |
| ***Lepiota subincarnata*** | Fatal Dapperling | ***Lepiota brunneoincarnata***, *Lepiota cristata*, *Marasmius oreades*, *Agaricus campestris* |

## Causes serious illness — `SERIOUS` (10)

Hospital treatment is usual.

| Species | Also known as | Confused with |
| --- | --- | --- |
| ***Amanita pantherina*** | Panther Cap | *Amanita rubescens*, *Amanita muscaria* |
| ***Entoloma sinuatum*** | Livid Pinkgill, Livid Entoloma | *Clitopilus prunulus*, *Calocybe gambosa*, *Agaricus arvensis* |
| ***Inocybe geophylla*** | White Fibrecap | ***Inocybe erubescens***, ***Clitocybe rivulosa***, ***Clitocybe dealbata***, ***Amanita virosa*** (+1) |
| ***Inocybe lilacina*** | Lilac Fibrecap | *Inocybe geophylla*, ***Inocybe erubescens***, *Laccaria amethystina*, *Mycena pura* (+1) |
| ***Paxillus involutus*** | Brown Roll-rim | *Lactarius deliciosus*, ***Clitocybe rivulosa*** |
| ***Pleurocybella porrigens*** | Angel's Wings | *Pleurotus ostreatus*, *Crepidotus mollis* |
| ***Pseudosperma rimosum*** | Split Fibrecap | ***Inocybe erubescens***, *Inocybe geophylla*, *Inocybe lilacina*, *Hebeloma crustuliniforme* (+2) |
| ***Rubroboletus satanas*** | Devil's Bolete | *Boletus edulis* |
| ***Tricholoma equestre*** | Yellow Knight, Man on Horseback | ***Amanita phalloides***, *Russula ochroleuca* |
| ***Tricholoma pardinum*** | Leopard Knight | *Tricholoma equestre*, *Calocybe gambosa*, *Clitocybe nebularis* |

## Causes illness — `TOXIC` (69)

Poisoning is reported.

| Species | Also known as | Confused with |
| --- | --- | --- |
| ***Agaricus xanthodermus*** | Yellow Stainer | *Agaricus campestris*, *Agaricus arvensis* |
| ***Amanita fulva*** | Tawny Grisette | ***Amanita phalloides***, ***Amanita virosa***, *Amanita rubescens*, *Volvopluteus gloiocephalus* |
| ***Amanita gemmata*** | Jewelled Amanita | *Amanita pantherina*, *Amanita muscaria*, *Amanita citrina* |
| ***Amanita muscaria*** | Fly Agaric | *Amanita rubescens*, *Russula emetica* |
| ***Amanita rubescens*** | The Blusher | *Amanita muscaria*, ***Amanita phalloides*** |
| ***Amanita vaginata*** | Grisette | ***Amanita phalloides***, ***Amanita virosa***, *Amanita fulva*, *Volvopluteus gloiocephalus* |
| ***Ampulloclitocybe clavipes*** | Club Foot | *Clitocybe nebularis*, ***Clitocybe rivulosa***, *Infundibulicybe gibba*, *Paralepista flaccida* |
| ***Armillaria mellea*** | Honey Fungus | ***Galerina marginata***, *Hypholoma fasciculare*, *Kuehneromyces mutabilis* |
| ***Chalciporus piperatus*** | Peppery Bolete | *Boletus edulis*, *Neoboletus luridiformis*, *Rubroboletus satanas*, *Imleria badia* (+1) |
| ***Chlorophyllum brunneum*** | Shaggy Parasol | *Macrolepiota procera* |
| ***Chlorophyllum rhacodes*** | Shaggy Parasol | *Chlorophyllum brunneum*, *Macrolepiota procera*, ***Amanita phalloides***, ***Lepiota brunneoincarnata*** |
| ***Clitocybe fragrans*** | Fragrant Funnel | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Infundibulicybe gibba* |
| ***Clitocybe metachroa*** | Twotone Funnel | ***Clitocybe dealbata***, ***Clitocybe rivulosa***, *Clitocybe fragrans*, *Clitocybe nebularis* |
| ***Clitocybe nebularis*** | Clouded Funnel, Clouded Agaric | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Entoloma sinuatum*, *Lepista nuda* |
| ***Clitocybe vibecina*** | Mealy Funnel | ***Clitocybe dealbata***, ***Clitocybe rivulosa***, *Clitocybe fragrans*, *Clitocybe metachroa* |
| ***Collybiopsis peronata*** | Wood Woollyfoot | *Gymnopus dryophilus*, *Collybiopsis confluens*, *Marasmius oreades* |
| ***Coprinopsis atramentaria*** | Common Inkcap | *Coprinus comatus* |
| ***Entoloma conferendum*** | Star Pinkgill | *Entoloma sinuatum*, *Pluteus cervinus*, *Clitopilus prunulus* |
| ***Entoloma rhodopolium*** | Wood Pinkgill | *Entoloma sinuatum*, *Entoloma sericeum*, *Clitopilus prunulus*, *Clitocybe nebularis* |
| ***Entoloma sericeum*** | Silky Pinkgill | *Entoloma sinuatum*, *Entoloma conferendum*, *Marasmius oreades*, *Clitopilus prunulus* |
| ***Galerina hypnorum*** | Moss Bell | ***Galerina marginata*** |
| ***Hebeloma crustuliniforme*** | Poison Pie | ***Clitocybe rivulosa***, *Agaricus campestris*, *Entoloma sinuatum*, *Inocybe geophylla* |
| ***Helvella crispa*** | White Saddle | ***Gyromitra esculenta***, *Morchella esculenta*, *Verpa bohemica* |
| ***Hygrocybe conica*** | Blackening Waxcap | *Gliophorus psittacinus*, *Cuphophyllus pratensis* |
| ***Hygrophoropsis aurantiaca*** | False Chanterelle | *Cantharellus cibarius*, *Omphalotus olearius* |
| ***Hypholoma fasciculare*** | Sulphur Tuft | *Kuehneromyces mutabilis*, *Armillaria mellea*, ***Galerina marginata*** |
| ***Infundibulicybe geotropa*** | Trooping Funnel | *Clitocybe nebularis*, *Infundibulicybe gibba*, ***Clitocybe rivulosa***, *Paralepista flaccida* |
| ***Infundibulicybe gibba*** | Common Funnel | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Paralepista flaccida*, *Clitocybe fragrans* |
| ***Lactarius blennius*** | Beech Milkcap | *Lactarius torminosus*, *Lactarius deliciosus*, *Lactarius quietus* |
| ***Lactarius glyciosmus*** | Coconut Milkcap | *Lactarius torminosus*, *Lactarius deliciosus*, *Lactarius quietus* |
| ***Lactarius pyrogalus*** | Fiery Milkcap | *Lactarius torminosus*, *Lactarius deliciosus*, *Lactarius quietus* |
| ***Lactarius rufus*** | Rufous Milkcap | *Lactarius torminosus*, *Lactarius deliciosus*, *Lactarius quietus* |
| ***Lactarius torminosus*** | Woolly Milkcap | *Lactarius deliciosus* |
| ***Lactarius turpis*** | Ugly Milkcap | *Lactarius torminosus*, *Lactarius deliciosus*, *Lactarius quietus* |
| ***Laetiporus sulphureus*** | Chicken of the Woods | — |
| ***Leotia lubrica*** | Jellybaby | *Clavulinopsis helvola* |
| ***Lepiota cristata*** | Stinking Dapperling | ***Lepiota brunneoincarnata***, ***Lepiota subincarnata***, *Macrolepiota procera* |
| ***Lepista nuda*** | Wood Blewit | *Cortinarius violaceus*, *Entoloma sinuatum* |
| ***Megacollybia platyphylla*** | Whitelaced Shank | *Hymenopellis radicata*, *Mucidula mucida*, *Pluteus cervinus*, *Armillaria mellea* |
| ***Mycena pura*** | Lilac Bonnet | *Laccaria amethystina*, *Cortinarius violaceus*, *Lepista nuda* |
| ***Mycena rosea*** | Rosy Bonnet | *Mycena pura*, *Laccaria amethystina*, *Lepista nuda* |
| ***Neoboletus luridiformis*** | Scarletina Bolete | *Rubroboletus satanas*, *Boletus edulis* |
| ***Neoboletus praestigiator*** | Deceiving Bolete | *Boletus edulis*, *Neoboletus luridiformis*, *Rubroboletus satanas*, *Imleria badia* (+2) |
| ***Omphalotus illudens*** | Jack o' Lantern | *Cantharellus cibarius*, *Hygrophoropsis aurantiaca*, *Omphalotus olearius* |
| ***Omphalotus olearius*** | Jack-o'-Lantern | *Cantharellus cibarius*, *Hygrophoropsis aurantiaca* |
| ***Panaeolina foenisecii*** | Brown Mottlegill | *Panaeolus papilionaceus*, *Panaeolus acuminatus*, *Psilocybe semilanceata*, ***Galerina marginata*** |
| ***Panaeolus acuminatus*** | Dewdrop Mottlegill | *Panaeolina foenisecii*, *Panaeolus papilionaceus*, *Psilocybe semilanceata* |
| ***Panaeolus papilionaceus*** | Petticoat Mottlegill | *Panaeolina foenisecii*, *Panaeolus acuminatus*, *Stropharia semiglobata*, *Psilocybe semilanceata* |
| ***Panellus stipticus*** | Bitter Oysterling | *Crepidotus mollis*, *Pleurotus ostreatus*, *Omphalotus illudens* |
| ***Paralepista flaccida*** | Tawny Funnel | *Clitocybe nebularis*, *Infundibulicybe gibba*, ***Clitocybe rivulosa***, *Hygrophoropsis aurantiaca* |
| ***Pholiota squarrosa*** | Shaggy Scalycap | ***Galerina marginata***, *Armillaria mellea* |
| ***Pluteus salicinus*** | Willow Shield | *Pluteus cervinus*, *Entoloma sinuatum*, ***Amanita phalloides*** |
| ***Psilocybe semilanceata*** | Liberty Cap | *Panaeolina foenisecii*, *Panaeolus acuminatus*, ***Galerina marginata***, *Marasmius oreades* |
| ***Rhodocollybia maculata*** | Spotted Toughshank | *Rhodocollybia butyracea*, *Gymnopus dryophilus*, *Clitocybe nebularis* |
| ***Russula betularum*** | Birch Brittlegill | *Russula cyanoxantha*, *Russula emetica*, *Russula nobilis*, *Russula ochroleuca* |
| ***Russula emetica*** | The Sickener | *Russula cyanoxantha*, *Amanita muscaria* |
| ***Russula fellea*** | Geranium Brittlegill | *Russula cyanoxantha*, *Russula emetica*, *Russula nobilis*, *Russula ochroleuca* |
| ***Russula fragilis*** | Fragile Brittlegill | *Russula cyanoxantha*, *Russula emetica*, *Russula nobilis*, *Russula ochroleuca* |
| ***Russula nobilis*** | Beechwood Sickener | *Russula emetica*, *Russula cyanoxantha*, *Russula ochroleuca* |
| ***Scleroderma citrinum*** | Common Earthball | *Lycoperdon perlatum*, *Calvatia gigantea* |
| ***Scleroderma verrucosum*** | Scaly Earthball | *Scleroderma citrinum*, *Lycoperdon perlatum*, ***Amanita virosa***, *Calvatia gigantea* |
| ***Stropharia semiglobata*** | Dung Roundhead | *Panaeolus papilionaceus*, *Bolbitius titubans*, *Psilocybe semilanceata* |
| ***Tricholoma fulvum*** | Birch Knight | *Tricholoma equestre*, *Tricholoma pardinum*, *Hebeloma crustuliniforme* |
| ***Tricholoma saponaceum*** | Soapy Knight | *Tricholoma terreum*, *Tricholoma pardinum*, *Tricholoma sulphureum*, *Tricholoma equestre* |
| ***Tricholoma sulphureum*** | Sulphur Knight | *Tricholoma equestre*, *Tricholoma saponaceum*, *Tricholoma pardinum* |
| ***Tricholoma terreum*** | Grey Knight | *Tricholoma pardinum*, *Tricholoma saponaceum*, *Tricholoma equestre* |
| ***Tricholoma ustale*** | Burnt Knight | *Tricholoma fulvum*, *Tricholoma equestre*, *Tricholoma pardinum* |
| ***Verpa bohemica*** | Early Morel, Thimble Morel | *Morchella esculenta*, ***Gyromitra esculenta*** |
| ***Volvopluteus gloiocephalus*** | Stubble Rosegill | ***Amanita phalloides***, ***Amanita virosa***, *Agaricus arvensis* |

## Not assessed as safe — `INEDIBLE` (157)

The risk has not been assessed. This is the safest value in the system, not a recommendation.

| Species | Also known as | Confused with |
| --- | --- | --- |
| ***Agaricus arvensis*** | Horse Mushroom | ***Amanita virosa***, ***Amanita phalloides***, *Agaricus xanthodermus* |
| ***Agaricus campestris*** | Field Mushroom | ***Amanita phalloides***, ***Amanita virosa***, *Agaricus xanthodermus* |
| ***Agaricus sylvaticus*** | Blushing Wood Mushroom | *Agaricus campestris*, *Agaricus arvensis*, *Agaricus xanthodermus*, ***Amanita phalloides*** (+1) |
| ***Amanita citrina*** | False Deathcap | ***Amanita phalloides***, ***Amanita virosa***, *Amanita rubescens* |
| ***Amanita excelsa*** | Grey Spotted Amanita | *Amanita pantherina*, *Amanita rubescens*, ***Amanita phalloides*** |
| ***Apioperdon pyriforme*** | Stump Puffball | *Lycoperdon perlatum*, *Scleroderma citrinum*, *Calvatia gigantea* |
| ***Ascocoryne sarcoides*** | Purple Jellydisc | *Chlorociboria aeruginascens*, *Bulgaria inquinans* |
| ***Atheniella flavoalba*** | Ivory Bonnet | — |
| ***Auricularia auricula-judae*** | Jelly Ear, Wood Ear | — |
| ***Bjerkandera adusta*** | Smoky Bracket | *Trametes versicolor*, *Daedaleopsis confragosa* |
| ***Bolbitius titubans*** | Yellow Fieldcap | *Stropharia semiglobata*, *Panaeolus papilionaceus* |
| ***Boletus edulis*** | Penny Bun, Cep, Porcini | *Tylopilus felleus*, *Rubroboletus satanas* |
| ***Bulgaria inquinans*** | Black Bulgar | *Exidia glandulosa*, *Ascocoryne sarcoides* |
| ***Byssomerulius corium*** | Netted Crust | — |
| ***Calocera cornea*** | Small Stagshorn | *Calocera viscosa*, *Dacrymyces stillatus*, *Calocera pallidospathulata* |
| ***Calocera pallidospathulata*** | Pale Stagshorn | *Calocera cornea*, *Calocera viscosa* |
| ***Calocera viscosa*** | Yellow Stagshorn | *Tremella mesenterica*, *Dacrymyces stillatus* |
| ***Calocybe gambosa*** | St George's Mushroom | ***Inocybe erubescens***, *Entoloma sinuatum*, ***Clitocybe rivulosa*** |
| ***Calvatia gigantea*** | Giant Puffball | *Scleroderma citrinum* |
| ***Cantharellus cibarius*** | Chanterelle, Girolle | *Hygrophoropsis aurantiaca*, ***Cortinarius rubellus***, *Omphalotus olearius* |
| ***Cerioporus squamosus*** | Dryad's Saddle, Pheasant's Back | — |
| ***Chlorociboria aeruginascens*** | Green Elfcup | *Ascocoryne sarcoides* |
| ***Chondrostereum purpureum*** | Silverleaf Fungus | *Stereum hirsutum*, *Trichaptum abietinum* |
| ***Clavulina cinerea*** | Grey Coral | *Clavulina coralloides*, *Clavulina rugosa* |
| ***Clavulina coralloides*** | Crested Coral | *Clavulina cinerea*, *Clavulina rugosa*, *Clavulinopsis corniculata* |
| ***Clavulina rugosa*** | Wrinkled Club | *Clavulina coralloides*, *Clavulinopsis helvola* |
| ***Clavulinopsis corniculata*** | Meadow Coral | *Clavulinopsis helvola*, *Clavulina coralloides* |
| ***Clavulinopsis helvola*** | Yellow Club | *Clavulinopsis corniculata*, *Calocera viscosa*, *Leotia lubrica* |
| ***Clitopilus prunulus*** | The Miller | *Entoloma sinuatum*, ***Clitocybe rivulosa*** |
| ***Collybiopsis confluens*** | Clustered Toughshank | *Collybiopsis peronata*, *Gymnopus dryophilus*, *Marasmius oreades* |
| ***Collybiopsis ramealis*** | Twig Parachute | *Marasmius rotula*, *Gymnopus dryophilus* |
| ***Coprinellus disseminatus*** | Fairy Inkcap | *Coprinellus micaceus*, *Coprinopsis lagopus*, *Parasola plicatilis*, ***Galerina marginata*** |
| ***Coprinellus micaceus*** | Glistening Inkcap | ***Galerina marginata***, *Kuehneromyces mutabilis*, *Coprinopsis atramentaria*, *Coprinus comatus* (+1) |
| ***Coprinopsis lagopus*** | Hare'sfoot Inkcap | *Coprinopsis atramentaria*, *Coprinellus micaceus*, *Coprinus comatus* |
| ***Coprinus comatus*** | Shaggy Inkcap, Lawyer's Wig | *Coprinopsis atramentaria* |
| ***Cortinarius anomalus*** | Variable Webcap | ***Cortinarius orellanus***, ***Cortinarius rubellus***, *Cortinarius violaceus*, *Lepista nuda* |
| ***Cortinarius violaceus*** | Violet Webcap | *Lepista nuda* |
| ***Craterellus cornucopioides*** | Horn of Plenty, Black Trumpet | — |
| ***Crepidotus cesatii*** | Roundspored Oysterling | *Crepidotus variabilis*, *Crepidotus mollis* |
| ***Crepidotus mollis*** | Peeling Oysterling | *Pleurotus ostreatus* |
| ***Crepidotus variabilis*** | Variable Oysterling | *Crepidotus mollis*, *Crepidotus cesatii*, *Panellus stipticus* |
| ***Cuphophyllus pratensis*** | Meadow Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Cuphophyllus virgineus* |
| ***Cuphophyllus virgineus*** | Snowy Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Marasmius oreades*, ***Amanita virosa*** |
| ***Cystoderma amianthinum*** | Earthy Powdercap | *Lepiota cristata*, ***Lepiota brunneoincarnata***, *Macrolepiota procera* |
| ***Dacrymyces stillatus*** | Common Jellyspot | *Tremella mesenterica*, *Calocera viscosa* |
| ***Daedaleopsis confragosa*** | Blushing Bracket | *Trametes versicolor* |
| ***Daldinia concentrica*** | King Alfred's Cakes, Cramp Balls | — |
| ***Datronia mollis*** | Common Mazegill | *Daedaleopsis confragosa*, *Bjerkandera adusta* |
| ***Entoloma sericellum*** | Cream Pinkgill | *Entoloma sericeum*, *Entoloma sinuatum*, *Clitopilus prunulus* |
| ***Exidia glandulosa*** | Witches' Butter | *Exidia nucleata*, *Exidia thuretiana*, *Auricularia auricula-judae* |
| ***Exidia nucleata*** | Crystal Brain | *Exidia thuretiana*, *Exidia glandulosa*, *Tremella mesenterica* |
| ***Exidia thuretiana*** | White Brain | *Exidia nucleata*, *Tremella mesenterica* |
| ***Fistulina hepatica*** | Beefsteak Fungus | — |
| ***Flammulina velutipes*** | Velvet Shank | ***Galerina marginata***, *Kuehneromyces mutabilis*, *Hypholoma fasciculare*, *Armillaria mellea* |
| ***Fomes fomentarius*** | Hoof Fungus, Tinder Fungus | *Fomitopsis betulina* |
| ***Fomitopsis betulina*** | Birch Polypore, Razorstrop Fungus | *Fomes fomentarius* |
| ***Fuscoporia ferrea*** | Cinnamon Porecrust | *Schizopora paradoxa* |
| ***Ganoderma adspersum*** | Southern Bracket | *Ganoderma applanatum*, *Fomes fomentarius* |
| ***Ganoderma applanatum*** | Artist's Bracket | *Ganoderma adspersum*, *Fomes fomentarius* |
| ***Gliophorus irrigatus*** | Slimy Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Gliophorus psittacinus*, *Gliophorus laetus* |
| ***Gliophorus laetus*** | Heath Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Gliophorus psittacinus*, *Gliophorus irrigatus* |
| ***Gliophorus psittacinus*** | Parrot Waxcap | *Cuphophyllus pratensis*, *Hygrocybe conica* |
| ***Gymnopilus penetrans*** | Common Rustgill | ***Galerina marginata***, *Kuehneromyces mutabilis*, *Hypholoma fasciculare*, *Armillaria mellea* |
| ***Gymnopus androsaceus*** | Horsehair Parachute | *Marasmius rotula*, *Collybiopsis ramealis* |
| ***Gymnopus dryophilus*** | Russet Toughshank | *Marasmius oreades*, *Rhodocollybia butyracea*, *Armillaria mellea*, ***Galerina marginata*** |
| ***Gymnopus fusipes*** | Spindleshank | *Gymnopus dryophilus*, *Armillaria mellea*, *Collybiopsis confluens* |
| ***Heterobasidion annosum*** | Root Rot | *Fomes fomentarius*, *Ganoderma applanatum* |
| ***Hydnum repandum*** | Hedgehog Fungus, Wood Hedgehog | — |
| ***Hygrocybe ceracea*** | Butter Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Hygrocybe chlorophana*, *Hygrocybe insipida* |
| ***Hygrocybe chlorophana*** | Golden Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Hygrocybe ceracea*, *Hygrocybe conica* |
| ***Hygrocybe coccinea*** | Scarlet Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Hygrocybe punicea*, *Hygrocybe conica* |
| ***Hygrocybe insipida*** | Spangle Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Hygrocybe ceracea*, *Hygrocybe reidii* |
| ***Hygrocybe punicea*** | Crimson Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Hygrocybe coccinea*, *Hygrocybe conica* |
| ***Hygrocybe quieta*** | Oily Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Hygrocybe reidii*, *Cuphophyllus pratensis* |
| ***Hygrocybe reidii*** | Honey Waxcap | ***Clitocybe rivulosa***, ***Clitocybe dealbata***, *Hygrocybe quieta*, *Hygrocybe insipida* |
| ***Hymenochaete rubiginosa*** | Oak Curtain Crust | *Stereum hirsutum*, *Stereum gausapatum* |
| ***Hymenopellis radicata*** | Rooting Shank | *Megacollybia platyphylla*, *Mucidula mucida*, *Armillaria mellea* |
| ***Hypoxylon fragiforme*** | Beech Woodwart | *Hypoxylon fuscum*, *Daldinia concentrica* |
| ***Hypoxylon fuscum*** | Hazel Woodwart | *Hypoxylon fragiforme*, *Jackrogersella multiformis* |
| ***Imleria badia*** | Bay Bolete | *Boletus edulis*, *Neoboletus luridiformis*, *Rubroboletus satanas*, *Tylopilus felleus* (+1) |
| ***Jackrogersella multiformis*** | Birch Woodwart | *Hypoxylon fragiforme*, *Daldinia concentrica* |
| ***Kretzschmaria deusta*** | Brittle Cinder | *Xylaria polymorpha*, *Daldinia concentrica* |
| ***Kuehneromyces mutabilis*** | Sheathed Woodtuft | ***Galerina marginata***, *Hypholoma fasciculare*, *Armillaria mellea* |
| ***Laccaria amethystina*** | Amethyst Deceiver | *Lepista nuda*, *Cortinarius violaceus* |
| ***Laccaria laccata*** | Deceiver | *Laccaria amethystina*, *Inocybe geophylla*, *Marasmius oreades* |
| ***Lacrymaria lacrymabunda*** | Weeping Widow | *Psathyrella candolleana*, *Panaeolina foenisecii*, *Agaricus campestris* |
| ***Lactarius deliciosus*** | Saffron Milkcap | *Lactarius torminosus*, *Paxillus involutus* |
| ***Lactarius quietus*** | Oakbug Milkcap | *Lactarius torminosus*, *Lactarius deliciosus*, *Lactarius tabidus* |
| ***Lactarius subdulcis*** | Mild Milkcap | *Lactarius torminosus*, *Lactarius deliciosus*, *Lactarius quietus* |
| ***Lactarius tabidus*** | Birch Milkcap | *Lactarius quietus*, *Lactarius torminosus*, *Lactarius deliciosus* |
| ***Leccinum scabrum*** | Brown Birch Bolete | *Boletus edulis*, *Tylopilus felleus* |
| ***Lycoperdon excipuliforme*** | Pestle Puffball | *Lycoperdon perlatum*, *Lycoperdon nigrescens*, *Calvatia gigantea*, *Scleroderma citrinum* (+1) |
| ***Lycoperdon nigrescens*** | Dusky Puffball | *Lycoperdon perlatum*, *Scleroderma citrinum*, ***Amanita virosa***, *Lycoperdon excipuliforme* |
| ***Lycoperdon perlatum*** | Common Puffball | *Scleroderma citrinum*, ***Amanita virosa*** |
| ***Macrolepiota procera*** | Parasol Mushroom | *Chlorophyllum brunneum*, ***Amanita phalloides*** |
| ***Marasmius oreades*** | Fairy Ring Champignon | ***Clitocybe rivulosa***, ***Clitocybe dealbata*** |
| ***Marasmius rotula*** | Collared Parachute | *Collybiopsis ramealis*, *Marasmius oreades* |
| ***Meripilus giganteus*** | Giant Polypore | *Laetiporus sulphureus*, *Ganoderma adspersum* |
| ***Morchella esculenta*** | Morel | ***Gyromitra esculenta***, *Verpa bohemica* |
| ***Mucidula mucida*** | Porcelain Fungus | *Hymenopellis radicata*, *Megacollybia platyphylla*, *Pleurotus ostreatus* |
| ***Mycena arcangeliana*** | Angel's Bonnet | ***Galerina marginata*** |
| ***Mycena epipterygia*** | Yellowleg Bonnet | ***Galerina marginata*** |
| ***Mycena filopes*** | Iodine Bonnet | ***Galerina marginata*** |
| ***Mycena galericulata*** | Common Bonnet | ***Galerina marginata***, *Kuehneromyces mutabilis*, *Armillaria mellea* |
| ***Mycena galopus*** | Milking Bonnet | ***Galerina marginata*** |
| ***Mycena haematopus*** | Burgundydrop Bonnet | ***Galerina marginata*** |
| ***Mycena inclinata*** | Clustered Bonnet | ***Galerina marginata*** |
| ***Mycena leptocephala*** | Nitrous Bonnet | — |
| ***Mycena polygramma*** | Grooved Bonnet | ***Galerina marginata*** |
| ***Mycena sanguinolenta*** | Bleeding Bonnet | — |
| ***Mycena tenerrima*** | Frosty Bonnet | ***Galerina marginata*** |
| ***Mycena vitilis*** | Snapping Bonnet | ***Galerina marginata*** |
| ***Parasola plicatilis*** | Pleated Inkcap | *Coprinellus disseminatus*, *Coprinopsis lagopus*, *Panaeolina foenisecii* |
| ***Peniophora quercina*** | Oak Curtain Crust | — |
| ***Phallus impudicus*** | Stinkhorn, Common Stinkhorn | *Lycoperdon perlatum* |
| ***Phlebia radiata*** | Wrinkled Crust | — |
| ***Phlebia tremellosa*** | Jelly Rot | *Phlebia radiata* |
| ***Phloeomana speirea*** | Bark Bonnet | ***Galerina marginata*** |
| ***Pleurotus ostreatus*** | Oyster Mushroom | *Omphalotus olearius*, *Crepidotus mollis* |
| ***Pluteus cervinus*** | Deer Shield | *Volvopluteus gloiocephalus*, *Entoloma sinuatum*, ***Amanita phalloides*** |
| ***Polyporus leptocephalus*** | Blackfoot Polypore | *Cerioporus squamosus*, *Trametes versicolor* |
| ***Postia caesia*** | Conifer Blueing Bracket | *Trametes versicolor* |
| ***Psathyrella candolleana*** | Pale Brittlestem | ***Galerina marginata***, *Psathyrella piluliformis*, *Hypholoma fasciculare*, *Coprinellus micaceus* |
| ***Psathyrella corrugis*** | Red Edge Brittlestem | *Psathyrella candolleana*, *Psathyrella piluliformis*, ***Galerina marginata*** |
| ***Psathyrella piluliformis*** | Common Stump Brittlestem | ***Galerina marginata***, *Psathyrella candolleana*, *Hypholoma fasciculare*, *Kuehneromyces mutabilis* |
| ***Rhodocollybia butyracea*** | Butter Cap | *Gymnopus dryophilus*, *Marasmius oreades*, *Clitocybe nebularis* |
| ***Rickenella fibula*** | Orange Mosscap | — |
| ***Russula atropurpurea*** | Purple Brittlegill | *Russula cyanoxantha*, *Russula emetica*, *Russula nobilis* |
| ***Russula cyanoxantha*** | Charcoal Burner | ***Amanita phalloides***, *Russula emetica* |
| ***Russula nigricans*** | Blackening Brittlegill | *Russula cyanoxantha*, *Russula nobilis*, *Russula emetica* |
| ***Russula ochroleuca*** | Ochre Brittlegill | *Tricholoma equestre*, *Russula cyanoxantha* |
| ***Russula vesca*** | The Flirt | *Russula cyanoxantha*, *Russula emetica*, *Russula nobilis*, *Russula ochroleuca* |
| ***Sarcoscypha austriaca*** | Scarlet Elfcup | — |
| ***Schizopora paradoxa*** | Split Porecrust | — |
| ***Scutellinia scutellata*** | Common Eyelash | *Sarcoscypha austriaca* |
| ***Sparassis crispa*** | Wood Cauliflower | — |
| ***Stereum gausapatum*** | Bleeding Oak Crust | *Stereum rugosum*, *Stereum hirsutum* |
| ***Stereum hirsutum*** | Hairy Curtain Crust | *Trametes versicolor* |
| ***Stereum rugosum*** | Bleeding Broadleaf Crust | *Stereum hirsutum*, *Trametes versicolor* |
| ***Suillus bovinus*** | Bovine Bolete | *Suillus luteus*, *Suillus granulatus*, *Suillus grevillei*, *Boletus edulis* (+1) |
| ***Suillus granulatus*** | Weeping Bolete | *Suillus luteus* |
| ***Suillus grevillei*** | Larch Bolete | *Suillus luteus*, *Suillus granulatus*, *Suillus bovinus*, *Boletus edulis* (+1) |
| ***Suillus luteus*** | Slippery Jack | *Suillus granulatus* |
| ***Trametes gibbosa*** | Lumpy Bracket | *Trametes versicolor*, *Daedaleopsis confragosa* |
| ***Trametes versicolor*** | Turkeytail | — |
| ***Tremella mesenterica*** | Yellow Brain | *Calocera viscosa*, *Auricularia auricula-judae*, *Dacrymyces stillatus* |
| ***Trichaptum abietinum*** | Purplepore Bracket | *Trametes versicolor*, *Bjerkandera adusta* |
| ***Tricholomopsis rutilans*** | Plums and Custard | *Tricholoma equestre*, *Gymnopilus penetrans*, *Armillaria mellea* |
| ***Tubaria furfuracea*** | Scurfy Twiglet | ***Galerina marginata***, *Kuehneromyces mutabilis*, *Psathyrella candolleana* |
| ***Tylopilus felleus*** | Bitter Bolete | *Boletus edulis* |
| ***Vuilleminia comedens*** | Waxy Crust | — |
| ***Xerocomellus chrysenteron*** | Red Cracking Bolete | *Imleria badia*, *Boletus edulis*, *Neoboletus luridiformis*, *Rubroboletus satanas* |
| ***Xerocomus subtomentosus*** | Suede Bolete | *Boletus edulis*, *Neoboletus luridiformis*, *Rubroboletus satanas*, *Imleria badia* (+2) |
| ***Xylaria carpophila*** | Beechmast Candlesnuff | *Xylaria hypoxylon* |
| ***Xylaria hypoxylon*** | Candlesnuff Fungus | *Daldinia concentrica* |
| ***Xylaria polymorpha*** | Dead Man's Fingers | *Xylaria hypoxylon*, *Kretzschmaria deusta* |
| ***Xylodon sambuci*** | Elder Whitewash | — |

---

Species in **bold** under *Confused with* can kill. A row naming one is a
pair the app refuses to resolve from a photograph.
