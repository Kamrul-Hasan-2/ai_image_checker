"""
CLIP Service for fast image analysis:
- Category & risk scoring
- Brand/logo similarity
- Promo banner detection
"""

import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import numpy as np
from typing import List, Dict, Tuple
import cv2


class CLIPService:
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        """Initialize CLIP model and processor"""
        print(f"Loading CLIP model: {model_name}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.model.eval()  # Set to evaluation mode for better inference
        self.processor = CLIPProcessor.from_pretrained(model_name)
        print(f"CLIP model loaded on {self.device}")
        
        # Temperature scaling for better calibration
        self.temperature = 1.0
        
        # Illegal products list (ONLY truly dangerous items)
        self.illegal_products = [
            "real loaded gun firearm weapon", "real pistol handgun with trigger", 
            "real rifle assault weapon", "real shotgun firearm",
            "naked nude woman explicit content", "pornographic sexual explicit image",
            "nude adult explicit photo",
            "heroin drug narcotic substance", "cocaine drug powder",
            "yaba drug pills tablets", "marijuana cannabis drug"
        ]
        
        # Risk categories
        self.risk_categories = [
            "safe general content",
            "promotional advertisement",
            "weapons or firearms",
            "medical drugs or substances",
            "financial stock trading",
            "violent or graphic content"
        ]
        
    def _preprocess_for_text_detection(self, image: Image.Image) -> List[Image.Image]:
        """Generate multiple preprocessed versions to enhance text/watermark visibility"""
        preprocessed = []
        
        # Original
        preprocessed.append(image)
        
        # High contrast version (helps detect watermarks)
        enhancer = ImageEnhance.Contrast(image)
        high_contrast = enhancer.enhance(2.0)
        preprocessed.append(high_contrast)
        
        # Sharpened version (enhances text edges)
        sharpened = image.filter(ImageFilter.SHARPEN)
        preprocessed.append(sharpened)
        
        # Brightness adjusted (helps with faded watermarks)
        brightness = ImageEnhance.Brightness(image)
        brightened = brightness.enhance(1.3)
        preprocessed.append(brightened)
        
        return preprocessed
    
    def _analyze_image_regions(self, image: Image.Image) -> List[Image.Image]:
        """Split image into regions to detect watermarks in specific locations"""
        regions = []
        width, height = image.size
        
        # Full image
        regions.append(image)
        
        # Bottom region (common watermark location)
        bottom_region = image.crop((0, int(height * 0.7), width, height))
        regions.append(bottom_region)
        
        # Top region
        top_region = image.crop((0, 0, width, int(height * 0.3)))
        regions.append(top_region)
        
        # Center region
        center_region = image.crop((int(width * 0.2), int(height * 0.3), 
                                   int(width * 0.8), int(height * 0.7)))
        regions.append(center_region)
        
        return regions
    
    def check_illegal_content(self, image: Image.Image) -> Dict:
                "Computer  » PC & Laptop  » Used Laptop",
                "Computer  » PC & Laptop  » PC Builder",
                "Computer  » PC & Laptop  » Desktop PC",
                "Computer  » PC & Laptop  » Mini PC",
                "Computer  » PC & Laptop  » Graphics Tablet",
                "Computer  » PC & Laptop  » Signature Pad",
                "Computer  » PC & Laptop  » Stylus Pen",
                "Computer  » PC & Laptop  » Tablet",
                "Computer  » PC & Laptop  » Server",
                "Computer  » PC & Laptop  » Server Rack",
                "Computer  » PC & Laptop  » Computer Repair",
                "Computer  » PC Parts  » Processor",
                "Computer  » PC Parts  » Motherboard",
                "Computer  » PC Parts  » RAM",
                "Computer  » PC Parts  » Hard Disk",
                "Computer  » PC Parts  » SSD",
                "Computer  » PC Parts  » Graphics Card",
                "Computer  » PC Parts  » Mouse",
                "Computer  » PC Parts  » Keyboard",
                "Computer  » PC Parts  » DVD Writer",
                "Computer  » PC Parts  » Computer Casing",
                "Computer  » PC Parts  » CPU Cooler",
                "Computer  » PC Parts  » Internet Modem",
                "Computer  » PC Parts  » Webcam",
                "Computer  » PC Parts  » TV Card",
                "Computer  » PC Parts  » Pendrive",
                "Computer  » PC Parts  » PC Cable",
                "Computer  » PC Parts  » Power Supply",
                "Computer  » PC Parts  » USB Hub",
                "Computer  » PC Parts  » Card Reader",
                "Computer  » PC Parts  » Blank Disk",
                "Computer  » PC Parts  » Sound Card",
                "Computer  » PC Parts  » Thermal Paste",
                "Computer  » PC Parts  » Mouse Pad",
                "Computer  » Laptop Accessories  » Laptop Battery",
                "Computer  » Laptop Accessories  » Laptop Charger",
                "Computer  » Laptop Accessories  » Laptop Bag",
                "Computer  » Laptop Accessories  » Laptop Cooler",
                "Computer  » Laptop Accessories  » Laptop Display",
                "Computer  » Laptop Accessories  » Laptop Keyboard",
                "Computer  » Laptop Accessories  » Laptop Table",
                "Computer  » Networking  » Router",
                "Computer  » Networking  » Wireless Access Point",
                "Computer  » Networking  » Radio Link",
                "Computer  » Networking  » WiFi Repeater",
                "Computer  » Networking  » Network Switch",
                "Computer  » Networking  » WiFi Adapter",
                "Computer  » Networking  » Network Storage",
                "Computer  » Networking  » Patch Panel",
                "Computer  » Networking  » Network Cable",
                "Computer  » Networking  » Crimping Tool",
                "Computer  » Networking  » HDMI Extender",
                "Computer  » Networking  » Cable Tester",
                "Computer  » Networking  » RJ45 Connector",
                "Computer  » Networking  » Splicer Machine",
                "Computer  » Networking  » Wireless Antenna",
                "Computer  » Networking  » Media Converter",
                "Computer  » Networking  » KVM Switch",
                "Computer  » Networking  » Face Plate",
                "Computer  » Networking  » Networking Accessories",
                "Computer  » Networking  » Network Support",
                "Computer  » Projection  » Projector",
                "Computer  » Projection  » Digital Whiteboard",
                "Computer  » Projection  » Projector Screen",
                "Computer  » Projection  » Projector Mount",
                "Computer  » Projection  » Projector Lamp",
                "Computer  » Projection  » Wireless Presenter",
                "Computer  » Projection  » Projector Repair",
                "Computer  » Projection  » Projector Rental",
                "Computer  » Projection  » Projector Accessories",
                "Computer  » Monitor  » Monitor",
                "Computer  » Print & Scan  » Photocopier",
                "Computer  » Print & Scan  » Printer",
                "Computer  » Print & Scan  » Scanner",
                "Computer  » Print & Scan  » Banner Printer",
                "Computer  » Print & Scan  » POS Printer",
                "Computer  » Print & Scan  » POS Machine",
                "Computer  » Print & Scan  » Barcode Printer",
                "Computer  » Print & Scan  » Barcode Scanner",
                "Computer  » Print & Scan  » ID Card Printer",
                "Computer  » Print & Scan  » Digital Duplicator",
                "Computer  » Print & Scan  » Cartridge",
                "Computer  » Print & Scan  » Thermal Paper Roll",
                "Computer  » Print & Scan  » PVC Card",
                "Computer  » Print & Scan  » Printer Paper",
                "Computer  » Print & Scan  » Printer Parts",
                "Computer  » Print & Scan  » Copier Repair",
                "Computer  » Print & Scan  » Printer Repair",
                "Computer  » Print & Scan  » Copier Parts",
                "Computer  » Print & Scan  » Printing Accessories",
                "Computer  » Office Electronics  » Paper Shredder",
                "Computer  » Office Electronics  » Money Counting Machine",
                "Computer  » Office Electronics  » Cash Register",
                "Computer  » Office Electronics  » Cash Drawer",
                "Computer  » Office Electronics  » Fake Note Detector",
                "Computer  » Office Electronics  » Laminating Machine",
                "Computer  » Office Electronics  » Spiral Binding Machine",
                "Computer  » Office Electronics  » Paper Cutting Machine",
                "Computer  » Software  » Antivirus",
                "Computer  » Software  » App Development",
                "Computer  » Software  » Business Software",
                "Computer  » Software  » POS Software",
                "Computer  » Software  » Inventory Software",
                "Computer  » Software  » Accounting Software",
                "Computer  » Software  » e-Commerce Website",
                "Computer  » Software  » Microsoft Office",
                "Computer  » Software  » Educational Software",
                "Computer  » Software  » Microsoft Windows",
                "Computer  » Web Service  » Web Hosting",
                "Computer  » Web Service  » Domain Name",
                "Computer  » Digital Marketing  » Digital Display",
                "Computer  » Digital Marketing  » Digital Marketing Service",
                "Computer  » Digital Marketing  » LED Sign Board",
                "Electronics  » Cooling & Heating  » Air Conditioner",
                "Electronics  » Cooling & Heating  » AC Ton Calculator",
                "Electronics  » Cooling & Heating  » AC Bill Calculator",
                "Electronics  » Cooling & Heating  » AC Accessories",
                "Electronics  » Cooling & Heating  » Air Curtain",
                "Electronics  » Cooling & Heating  » Air Cooler",
                "Electronics  » Cooling & Heating  » Room Heater",
                "Electronics  » Cooling & Heating  » Fan",
                "Electronics  » Cooling & Heating  » Air Purifier",
                "Electronics  » Cooling & Heating  » Humidifier",
                "Electronics  » Cooling & Heating  » Dehumidifier",
                "Electronics  » Cooling & Heating  » Water Heater & Geyser",
                "Electronics  » TV & Video  » Television",
                "Electronics  » TV & Video  » TV Size Calculator",
                "Electronics  » TV & Video  » Android TV Box",
                "Electronics  » TV & Video  » Air Mouse",
                "Electronics  » TV & Video  » Wireless Display Adapter",
                "Electronics  » TV & Video  » 3D Glass",
                "Electronics  » TV & Video  » Satellite Dish",
                "Electronics  » TV & Video  » TV Accessories",
                "Electronics  » TV & Video  » TV Remote",
                "Electronics  » TV & Video  » TV Bracket",
                "Electronics  » TV & Video  » Game Console",
                "Electronics  » TV & Video  » Game Controller",
                "Electronics  » TV & Video  » Game Accessories",
                "Electronics  » TV & Video  » TV Repair Service",
                "Electronics  » Home Appliance  » Water Filter",
                "Electronics  » Home Appliance  » Filter Accessories",
                "Electronics  » Home Appliance  » Electric Chula",
                "Electronics  » Home Appliance  » Dishwasher",
                "Electronics  » Home Appliance  » Refrigerator",
                "Electronics  » Home Appliance  » Washing Machine",
                "Electronics  » Home Appliance  » Microwave Oven",
                "Electronics  » Home Appliance  » Blender",
                "Electronics  » Home Appliance  » Air Diffuser",
                "Electronics  » Home Appliance  » Air Fryer",
                "Electronics  » Home Appliance  » Coffee Machine",
                "Electronics  » Home Appliance  » Toaster",
                "Electronics  » Home Appliance  » Iron",
                "Electronics  » Home Appliance  » Food Maker",
                "Electronics  » Home Appliance  » Electric Kettle",
                "Electronics  » Home Appliance  » Vacuum Cleaner",
                "Electronics  » Home Appliance  » Rice Cooker",
                "Electronics  » Home Appliance  » Thermos Container",
                "Electronics  » Home Appliance  » Sewing Machine",
                "Electronics  » Home Appliance  » Dispenser",
                "Electronics  » Home Appliance  » Gas Stove",
                "Electronics  » Home Appliance  » Kitchen Hood",
                "Electronics  » Home Appliance  » Roti Maker",
                "Electronics  » Home Appliance  » Barbeque Grill",
                "Electronics  » Home Appliance  » Bathroom Supplies",
                "Electronics  » Home Appliance  » Kitchen Storage",
                "Electronics  » Camera & Photo  » Digital Camera",
                "Electronics  » Camera & Photo  » DSLR",
                "Electronics  » Camera & Photo  » Action Camera",
                "Electronics  » Camera & Photo  » Mirrorless Camera",
                "Electronics  » Camera & Photo  » Instant Camera",
                "Electronics  » Camera & Photo  » Video Camera",
                "Electronics  » Camera & Photo  » Digital Photo Frame",
                "Electronics  » Camera & Photo  » Binocular",
                "Electronics  » Camera & Photo  » Telescope",
                "Electronics  » Camera Accessories  » Camera Lens",
                "Electronics  » Camera Accessories  » Camera Flash",
                "Electronics  » Camera Accessories  » Studio Light",
                "Electronics  » Camera Accessories  » Camera Battery",
                "Electronics  » Camera Accessories  » Camera Charger",
                "Electronics  » Camera Accessories  » Memory Card",
                "Electronics  » Camera Accessories  » Camera Tripod",
                "Electronics  » Camera Accessories  » Lens Cleaning Kit",
                "Electronics  » Camera Accessories  » Camera Bag",
                "Electronics  » Camera Accessories  » Lens Hood",
                "Electronics  » Mobile  » Mobile Phone",
                "Electronics  » Mobile Accessories  » Power Bank",
                "Electronics  » Mobile Accessories  » Mobile Battery",
                "Electronics  » Mobile Accessories  » Data Cable",
                "Electronics  » Mobile Accessories  » Mobile Phone Charger",
                "Electronics  » Mobile Accessories  » Wireless Charger",
                "Electronics  » Mobile Accessories  » Car Charger",
                "Electronics  » Mobile Accessories  » Selfie Stick",
                "Electronics  » Mobile Accessories  » Mobile Phone Cover",
                "Electronics  » Mobile Accessories  » Mobile Phone Camera Lens",
                "Electronics  » Mobile Accessories  » Mobile Signal Booster",
                "Electronics  » Mobile Accessories  » Mobile Holder",
                "Electronics  » Mobile Accessories  » Screen Protector",
                "Electronics  » Mobile Accessories  » VR Box",
                "Electronics  » Mobile Accessories  » Other Accessories",
                "Electronics  » Telephony  » Telephone Set",
                "Electronics  » Telephony  » IP Phone",
                "Electronics  » Telephony  » PABX System",
                "Electronics  » Telephony  » Fax Machine",
                "Electronics  » Telephony  » Telephone Accessories",
                "Electronics  » Telephony  » Walkie Talkie",
                "Electronics  » Home & Stage Audio  » Speaker",
                "Electronics  » Home & Stage Audio  » Headphone",
                "Electronics  » Home & Stage Audio  » AV Receiver",
                "Electronics  » Home & Stage Audio  » Amplifier",
                "Electronics  » Home & Stage Audio  » PA System",
                "Electronics  » Home & Stage Audio  » Audio Interface",
                "Electronics  » Home & Stage Audio  » Conference System",
                "Electronics  » Home & Stage Audio  » Microphone",
                "Electronics  » Home & Stage Audio  » Speaker Remote Control",
                "Electronics  » Portable Media  » Voice Recorder",
                "Electronics  » Portable Media  » Ebook Reader",
                "Electronics  » Portable Media  » Digital Dictionary",
                "Electronics  » Portable Media  » HDMI Splitter",
                "Electronics  » Portable Media  » MP3 Player",
                "Electronics  » Portable Media  » iPod Player",
                "Electronics  » Portable Media  » Calculator",
                "Electronics  » Portable Media  » Radio",
                "Security and Industry  » Access Security  » Biometric Attendance",
                "Security and Industry  » Access Security  » Fingerprint Scanner",
                "Security and Industry  » Access Security  » RFID Attendance",
                "Security and Industry  » Access Security  » Door Lock",
                "Security and Industry  » Access Security  » Metal Detector",
                "Security and Industry  » Access Security  » Archway Gate",
                "Security and Industry  » Access Security  » Security Alarm",
                "Security and Industry  » Access Security  » Baggage Scanner",
                "Security and Industry  » Access Security  » Car Search Mirror",
                "Security and Industry  » Access Security  » Mobile Phone Jammer",
                "Security and Industry  » Access Security  » RFID Card",
                "Security and Industry  » Access Security  » Barrier Gate",
                "Security and Industry  » Access Security  » Locker",
                "Security and Industry  » Access Security  » Guard Tour System",
                "Security and Industry  » Access Security  » Baton",
                "Security and Industry  » Access Security  » Door Exit Button",
                "Security and Industry  » Access Security  » Self Defence",
                "Security and Industry  » Security & Surveillance  » CCTV Camera",
                "Security and Industry  » Security & Surveillance  » CCTV Full Set",
                "Security and Industry  » Security & Surveillance  » NVR",
                "Security and Industry  » Security & Surveillance  » DVR",
                "Security and Industry  » Security & Surveillance  » CCTV Accessories",
                "Security and Industry  » Security & Surveillance  » Spy Camera",
                "Security and Industry  » Security & Surveillance  » Door Camera",
                "Security and Industry  » Security & Surveillance  » CCTV Camera Repair",
                "Security and Industry  » Fire Safety  » Fire Extinguisher",
                "Security and Industry  » Fire Safety  » Fire Alarm",
                "Security and Industry  » Fire Safety  » Fire Bucket",
                "Security and Industry  » Fire Safety  » Fire Ladder",
                "Security and Industry  » Fire Safety  » Fire Axe",
                "Security and Industry  » Fire Safety  » Hand Mike",
                "Security and Industry  » Fire Safety  » Fire Accessories",
                "Security and Industry  » Textile & Garments  » Ear Plug",
                "Security and Industry  » Textile & Garments  » Safety Shoes",
                "Security and Industry  » Textile & Garments  » Safety Helmet",
                "Security and Industry  » Textile & Garments  » Eye Wash Station",
                "Security and Industry  » Textile & Garments  » Spill Kit",
                "Security and Industry  » Textile & Garments  » Pantone Book",
                "Security and Industry  » Textile & Garments  » Color Matching Cabinet",
                "Security and Industry  » Textile & Garments  » Iron Table",
                "Security and Industry  » Textile & Garments  » Testing Instrument",
                "Security and Industry  » Textile & Garments  » GSM Cutter",
                "Security and Industry  » Textile & Garments  » Button Pull Tester",
                "Security and Industry  » Textile & Garments  » Textile Accessories",
                "Security and Industry  » Textile & Garments  » Hand Pallet",
                "Security and Industry  » Textile & Garments  » Needle Detector",
                "Security and Industry  » Textile & Garments  » Textile Machinery",
                "Security and Industry  » Textile & Garments  » Safety Belt",
                "Security and Industry  » Textile & Garments  » Crockmeter",
                "Security and Industry  » Textile & Garments  » Magnifying Glass",
                "Security and Industry  » Textile & Garments  » Detergent",
                "Security and Industry  » Textile & Garments  » Shipping Container",
                "Security and Industry  » Textile & Garments  » Security Seal",
                "Security and Industry  » Meter & Scale  » Weight Machine",
                "Security and Industry  » Meter & Scale  » Distance Meter",
                "Security and Industry  » Meter & Scale  » Gas Leak Detector",
                "Security and Industry  » Meter & Scale  » pH Meter",
                "Security and Industry  » Meter & Scale  » DO Meter",
                "Security and Industry  » Meter & Scale  » TDS Meter",
                "Security and Industry  » Meter & Scale  » Moisture Meter",
                "Security and Industry  » Meter & Scale  » Flow Meter",
                "Security and Industry  » Meter & Scale  » Multimeter",
                "Security and Industry  » Meter & Scale  » Lux Meter",
                "Security and Industry  » Meter & Scale  » Sound Level Meter",
                "Security and Industry  » Meter & Scale  » Tachometer",
                "Security and Industry  » Meter & Scale  » Insulation Tester",
                "Security and Industry  » Meter & Scale  » Anemometer",
                "Security and Industry  » Meter & Scale  » Hygrometer",
                "Security and Industry  » Meter & Scale  » Thickness Gauge",
                "Security and Industry  » Meter & Scale  » Refractometer",
                "Security and Industry  » Meter & Scale  » Caliper",
                "Security and Industry  » Meter & Scale  » Other Meters",
                "Security and Industry  » GPS  » GPS Tracker",
                "Security and Industry  » GPS  » GPS Navigation",
                "Security and Industry  » GPS  » Chartplotter",
                "Security and Industry  » GPS  » Fishfinder",
                "Security and Industry  » GPS  » Compass",
                "Security and Industry  » GPS  » Marine Radar",
                "Security and Industry  » Electrical Equipment  » IPS",
                "Security and Industry  » Electrical Equipment  » UPS",
                "Security and Industry  » Electrical Equipment  » Solar IPS",
                "Security and Industry  » Electrical Equipment  » Battery",
                "Security and Industry  » Electrical Equipment  » Solar Panel",
                "Security and Industry  » Electrical Equipment  » Light",
                "Security and Industry  » Electrical Equipment  » Generator",
                "Security and Industry  » Electrical Equipment  » Voltage Stabilizer",
                "Security and Industry  » Electrical Equipment  » Transformer",
                "Security and Industry  » Electrical Equipment  » Electrical Switch",
                "Security and Industry  » Electrical Equipment  » Module Board",
                "Security and Industry  » Electrical Equipment  » Surge Protector",
                "Security and Industry  » Electrical Equipment  » Calling Bell",
                "Security and Industry  » Electrical Equipment  » Multi Plug",
                "Security and Industry  » Electrical Equipment  » Electric Cable",
                "Security and Industry  » Electrical Equipment  » Lightning Arrester",
                "Security and Industry  » Electrical Equipment  » Turbine",
                "Security and Industry  » Water Equipment  » Life Jacket",
                "Security and Industry  » Water Equipment  » Fishing Rod",
                "Security and Industry  » Water Equipment  » Water Pump",
                "Security and Industry  » Water Equipment  » Water Tank",
                "Security and Industry  » Agricultural  » Grass Cutting Machine",
                "Security and Industry  » Agricultural  » Power Tiller",
                "Security and Industry  » Agricultural  » Milking Machine",
                "Security and Industry  » Agricultural  » Rice Harvester",
                "Security and Industry  » Agricultural  » Rice Transplanter",
                "Security and Industry  » Agricultural  » Chainsaw",
                "Security and Industry  » Agricultural  » Agricultural Machinery",
                "Security and Industry  » Agricultural  » Pesticide",
                "Security and Industry  » Agricultural  » Gardening Tools",
                "Security and Industry  » Poultry Equipment  » Incubator",
                "Security and Industry  » Poultry Equipment  » Incubator Temperature Controller",
                "Security and Industry  » Poultry Equipment  » Incubator Accessories",
                "Security and Industry  » Farm  » Animal",
                "Security and Industry  » Farm  » Pet Accessories",
                "Security and Industry  » Farm  » Cow",
                "Security and Industry  » Machine & Tools  » Heat Press Machine",
                "Security and Industry  » Machine & Tools  » Blower Machine",
                "Security and Industry  » Machine & Tools  » Cutting Plotter",
                "Security and Industry  » Machine & Tools  » Lift",
                "Security and Industry  » Machine & Tools  » Air Compressor",
                "Security and Industry  » Machine & Tools  » Boat Engine",
                "Security and Industry  » Machine & Tools  » Sealing Machine",
                "Security and Industry  » Machine & Tools  » Exhaust Fan",
                "Security and Industry  » Machine & Tools  » Chain Hoist",
                "Security and Industry  » Machine & Tools  » Silicone Rubber",
                "Security and Industry  » Machine & Tools  » Numbering Machine",
                "Security and Industry  » Machine & Tools  » Electric Motor",
                "Security and Industry  » Machine & Tools  » Ice Cream Machine",
                "Security and Industry  » Machine & Tools  » Tool Box",
                "Security and Industry  » Survey Equipment  » Total Station",
                "Security and Industry  » Survey Equipment  » Auto Level",
                "Security and Industry  » Survey Equipment  » Construction Pipe",
                "Security and Industry  » Survey Equipment  » Surveying Accessories",
                "Travels  » Air Ticket  » Air Ticket",
                "Travels  » Bus Ticket  » All Bus Ticket",
                "Travels  » Tour Package  » Tour Package",
                "Travels  » Umrah Package  » Umrah Package",
                "Travels  » Hajj Package  » Hajj Package",
                "Travels  » Hotel Booking  » Hotel Booking",
                "Travels  » Visa Processing  » Visa Processing Service",
                "Travels  » Doctor Appointment  » Indian Doctor Appointment",
                "Travels  » Train Ticket  » Train Ticket",
                "Travels  » Saint Martin Ship Ticket  » Saint Martin Ship Ticket",
                "Travels  » Jobs  » Jobs",
                "Health & Beauty  » Medical & Lab  » Hearing Aid",
                "Health & Beauty  » Medical & Lab  » Nebulizer Machine",
                "Health & Beauty  » Medical & Lab  » Pulse Oximeter",
                "Health & Beauty  » Medical & Lab  » Oxygen Concentrator",
                "Health & Beauty  » Medical & Lab  » Oxygen Cylinder",
                "Health & Beauty  » Medical & Lab  » Face Mask",
                "Health & Beauty  » Medical & Lab  » PPE",
                "Health & Beauty  » Medical & Lab  » Hearing Aid Battery",
                "Health & Beauty  » Medical & Lab  » Thermometer",
                "Health & Beauty  » Medical & Lab  » Hand Gloves",
                "Health & Beauty  » Medical & Lab  » Safety Goggles",
                "Health & Beauty  » Medical & Lab  » Blood Pressure Machine",
                "Health & Beauty  » Medical & Lab  » Stethoscope",
                "Health & Beauty  » Medical & Lab  » Diabetes Machine",
                "Health & Beauty  » Medical & Lab  » Massager Machine",
                "Health & Beauty  » Medical & Lab  » Therapy Machine",
                "Health & Beauty  » Medical & Lab  » Hospital Bed",
                "Health & Beauty  » Medical & Lab  » Cervical Collar",
                "Health & Beauty  » Medical & Lab  » Suction Machine",
                "Health & Beauty  » Medical & Lab  » Wheelchair",
                "Health & Beauty  » Medical & Lab  » Walking Stick",
                "Health & Beauty  » Medical & Lab  » ECG Machine",
                "Health & Beauty  » Medical & Lab  » Patient Monitor",
                "Health & Beauty  » Medical & Lab  » Commode Chair",
                "Health & Beauty  » Medical & Lab  » Ultrasonography Machine",
                "Health & Beauty  » Medical & Lab  » Alcohol Pad",
                "Health & Beauty  » Medical & Lab  » X-Ray Machine",
                "Health & Beauty  » Medical & Lab  » Surgical Light",
                "Health & Beauty  » Medical & Lab  » Disinfection Chamber",
                "Health & Beauty  » Medical & Lab  » Spray Machine",
                "Health & Beauty  » Medical & Lab  » Dental Treatment",
                "Health & Beauty  » Medical & Lab  » Microscope",
                "Health & Beauty  » Medical & Lab  » Sanitizer",
                "Health & Beauty  » Medical & Lab  » Biochemistry Analyzer",
                "Health & Beauty  » Medical & Lab  » CPAP Machine",
                "Health & Beauty  » Medical & Lab  » Anesthesia Machine",
                "Health & Beauty  » Medical & Lab  » Hot Water Bag",
                "Health & Beauty  » Medical & Lab  » First Aid",
                "Health & Beauty  » Medical & Lab  » Stretcher",
                "Health & Beauty  » Medical & Lab  » Labratory Equipment",
                "Health & Beauty  » Medical & Lab  » Medical Equipment",
                "Health & Beauty  » Medical & Lab  » Dental Instrument",
                "Health & Beauty  » Medical & Lab  » Condom",
                "Health & Beauty  » Medical & Lab  » Home Care",
                "Health & Beauty  » Medical & Lab  » Rental Service",
                "Health & Beauty  » Medical & Lab  » Ice Box",
                "Health & Beauty  » Food  » Fruits",
                "Health & Beauty  » Food  » Sweet",
                "Health & Beauty  » Food  » Mango",
                "Health & Beauty  » Food  » Khejur",
                "Health & Beauty  » Food  » Nuts",
                "Health & Beauty  » Food  » Herbs",
                "Health & Beauty  » Food  » Honey",
                "Health & Beauty  » Food  » Masala",
                "Health & Beauty  » Food  » Cooking Oil",
                "Health & Beauty  » Food  » Beverage",
                "Health & Beauty  » Food  » Gur",
                "Health & Beauty  » Food  » Ghee",
                "Health & Beauty  » Food  » Cheese",
                "Health & Beauty  » Food  » Fish",
                "Health & Beauty  » Food  » Biscuit",
                "Health & Beauty  » Food  » Chocolate",
                "Health & Beauty  » Health Care  » Gym Equipment",
                "Health & Beauty  » Health Care  » Herbal Medicine",
                "Health & Beauty  » Health Care  » Anti Snoring Aid",
                "Health & Beauty  » Health Care  » Electronic Cigarette",
                "Health & Beauty  » Hair Care  » Trimmer",
                "Health & Beauty  » Hair Care  » Hair Treatment",
                "Health & Beauty  » Hair Care  » Hair Straightener",
                "Health & Beauty  » Hair Care  » Hair Dryer",
                "Health & Beauty  » Hair Care  » Hair Shampoo",
                "Health & Beauty  » Cosmetics  » Soap",
                "Health & Beauty  » Cosmetics  » Essential Oil",
                "Health & Beauty  » Cosmetics  » Makeup Box",
                "Health & Beauty  » Cosmetics  » Mole Removal",
                "Health & Beauty  » Cosmetics  » Aloe Vera Gel",
                "Health & Beauty  » Cosmetics  » Skin Care Kit",
                "Health & Beauty  » Cosmetics  » Face Wash",
                "Health & Beauty  » Cosmetics  » Lipstick",
                "Health & Beauty  » Cosmetics  » Peel Off Mask",
                "Health & Beauty  » Watch  » Smart Watch",
                "Health & Beauty  » Watch  » Hand Watch",
                "Health & Beauty  » Watch  » Wall Clock",
                "Health & Beauty  » Watch  » Stopwatch",
                "Health & Beauty  » Lifestyle  » Umbrella",
                "Health & Beauty  » Lifestyle  » Raincoat",
                "Health & Beauty  » Lifestyle  » Jewelry",
                "Health & Beauty  » Lifestyle  » Clothing",
                "Health & Beauty  » Lifestyle  » Sunglass",
                "Health & Beauty  » Lifestyle  » Wallet",
                "Health & Beauty  » Lifestyle  » Card Holder",
                "Health & Beauty  » Lifestyle  » Bag",
                "Health & Beauty  » Lifestyle  » Gift Set",
                "Health & Beauty  » Lifestyle  » Perfume",
                "Health & Beauty  » Lifestyle  » Cap",
                "Health & Beauty  » Lifestyle  » Towel",
                "Health & Beauty  » Lifestyle  » Belt",
                "Health & Beauty  » Lifestyle  » Lighter",
                "Health & Beauty  » Lifestyle  » Nail Cutter",
                "Health & Beauty  » Kids and Mom  » Sports",
                "Health & Beauty  » Kids and Mom  » Drone",
                "Health & Beauty  » Kids and Mom  » Baby Feeder",
                "Health & Beauty  » Kids and Mom  » Shoes",
                "Health & Beauty  » Kids and Mom  » Dolna",
                "Health & Beauty  » Kids and Mom  » Diaper",
                "Health & Beauty  » Kids and Mom  » Toy",
                "Health & Beauty  » Kids and Mom  » Swimming Pool",
                "Health & Beauty  » Kids and Mom  » Baby Food",
                "Health & Beauty  » Kids and Mom  » Tent",
                "Health & Beauty  » Kids and Mom  » Hanger",
                "Health & Beauty  » Kids and Mom  » Toothbrush",
                "Health & Beauty  » Kids and Mom  » Baby Car",
                "Health & Beauty  » Kids and Mom  » Baby Stroller",
                "Health & Beauty  » Kids and Mom  » Baby Walker",
                "Health & Beauty  » Party Supplies  » Invitation Card",
                "Household  » Furniture  » Bed",
                "Household  » Furniture  » Bedside Table",
                "Household  » Furniture  » Air Bed",
                "Household  » Furniture  » Dining Table",
                "Household  » Furniture  » Dining Chair",
                "Household  » Furniture  » Sofa Set",
                "Household  » Furniture  » Center Table",
                "Household  » Furniture  » Divan",
                "Household  » Furniture  » Dressing Table",
                "Household  » Furniture  » Showcase",
                "Household  » Furniture  » Shelf",
                "Household  » Furniture  » Wardrobe",
                "Household  » Furniture  » Almirah",
                "Household  » Furniture  » Trolley",
                "Household  » Furniture  » Stool",
                "Household  » Furniture  » Furniture Set",
                "Household  » Furniture  » Kitchen Furniture",
                "Household  » Furniture  » Shoe Rack",
                "Household  » Office Furniture  » Office Table",
                "Household  » Office Furniture  » Chair",
                "Household  » Office Furniture  » Conference Table",
                "Household  » Office Furniture  » Display Rack",
                "Household  » Office Furniture  » Office Sofa",
                "Household  » Office Furniture  » Office Decor",
                "Household  » Bedding  » Bed Sheet",
                "Household  » Bedding  » Mosquito Net",
                "Household  » Bedding  » Mattress",
                "Household  » Bedding  » Pillow",
                "Household  » Bedding  » Cushion",
                "Household  » Bedding  » Sofa Foam",
                "Household  » Bedding  » Blanket",
                "Household  » Decoration  » Curtain",
                "Household  » Decoration  » Floor Mat",
                "Household  » Decoration  » Interior Design",
                "Household  » Decoration  » Showpiece",
                "Household  » Decoration  » Mirror",
                "Household  » Decoration  » Door",
                "Household  » Decoration  » Tiles",
                "Household  » Decoration  » Decor Accessories",
                "Household  » Decoration  » Organizer",
                "Household  » Furniture Accessories  » Furniture Accessories",
                "Household  » Household Cleaner  » Mop",
                "Household  » Household Cleaner  » Hose Pipe",
                "Household  » Household Cleaner  » Floor Cleaner",
                "Household  » Household Cleaner  » Glass Cleaner",
                "Household  » Household Cleaner  » Air Freshener",
                "Household  » Household Cleaner  » Basket",
                "Household  » Pest Control  » Mosquito Killer",
                "Household  » Pest Control  » Pest Control Service",
                "Household  » Kitchenware  » Crockeries",
                "Household  » Kitchenware  » Vegetable Cutter",
                "Household  » Kitchenware  » Fry Pan",
                "Household  » Kitchenware  » Korai",
                "Household  » Kitchenware  » Pressure Cooker",
                "Household  » Kitchenware  » Cup & Mug",
                "Household  » Kitchenware  » Water Bottle",
                "Household  » Kitchenware  » Kitchen Knife",
                "Household  » Stationery & Craft  » Paper NoteBook",
                "Household  » Stationery & Craft  » Wrapping Paper",
                "Household  » Stationery & Craft  » Stapler",
                "Household  » Stationery & Craft  » Scotch Tape",
                "Household  » Stationery & Craft  » Pen",
                "Household  » Stationery & Craft  » Measuring Tape",
                "Car & Bike  » Car  » Car",
                "Car & Bike  » Car Accessories  » Car Scratch Remover",
                "Car & Bike  » Car Accessories  » Engine Oil",
                "Car & Bike  » Car Accessories  » Car Scanner",
                "Car & Bike  » Bike  » Bike",
                "Car & Bike  » Bike Accessories  » Motorcycle Helmet",
                "Car & Bike  » Bike Accessories  » Motorcycle Tyre",
                "Car & Bike  » Three Wheeler  » CNG",
                "Car & Bike  » Three Wheeler  » Auto Rickshaw",
                "Car & Bike  » Bicycle  » Bicycle",
                "Car & Bike  » Bicycle Accessories  » All Bicycle Accessories",
                "Car & Bike  » Commercial Vehicle  » Boat",
                "Car & Bike  » Commercial Vehicle  » Truck",
                "Car & Bike  » Commercial Vehicle  » Tractor",
                "Car & Bike  » Commercial Vehicle  » Bus",
                "Car & Bike  » Rental  » Pickup Rental",
                "Car & Bike  » Rental  » Ambulance Service",
                "Car & Bike  » Vehicle Equipment  » All Vehicle Equipment",
                "Real Estate  » Apartment  » Apartment",
                "Real Estate  » Land  » Land",
                "Real Estate  » Commercial Space  » 1-1000 Sqft Office Space",
                "Real Estate  » Commercial Space  » 1001-2000 Sqft Office Space",
                "Real Estate  » Commercial Space  » 2000+ Sqft Office Space",
                "Real Estate  » Sanitary  » Commode",
                "Real Estate  » Sanitary  » Basin",
                "Real Estate  » Sanitary  » Water Tap",
                "Real Estate  » Construction Material  » Cement",
                "Real Estate  » Construction Material  » Sand",
                "Real Estate  » Construction Material  » Stone",
                "Real Estate  » Construction Material  » Brick",
                "Real Estate  » Construction Material  » Rod",
                "Real Estate  » Construction Material  » Construction Equipment",
                "More  » Islamic Zone  » Janamaz",
                "More  » Islamic Zone  » Tasbeeh",
                "More  » Book  » Al-Quran",
                "More  » Book  » Islamic Book",
                "More  » Book  » Education Book",
                "More  » Services  » Legal Service",
                "More  » Services  » Party Center Rental",
                "More  » Services  » House Shifting Service",
                "More  » Everything Else  » Online Media",
                "More  » Everything Else  » Everything Else"
            ]

        # Illegal products list
        # Bangladesh-specific illegal products (ONLY truly dangerous/inappropriate items)
        self.illegal_products = [
            # Real weapons only - very specific
            "real loaded gun firearm weapon", "real pistol handgun with trigger", 
            "real rifle assault weapon", "real shotgun firearm",
            
            # Adult/inappropriate content
            "naked nude woman explicit content", "pornographic sexual explicit image",
            "nude adult explicit photo",
            
            # Real drugs
            "heroin drug narcotic substance", "cocaine drug powder",
            "yaba drug pills tablets", "marijuana cannabis drug"
        ]
        
        # Define risk categories (NEW REQUIREMENTS)
        self.risk_categories = [
            "safe general content",
            "promotional advertisement",
            "weapons or firearms",
            "medical drugs or substances",
            "financial stock trading",
            "violent or graphic content"
        ]
        
        # Promo banner indicators (focus on ACTUAL promotional content, not brand names)
        self.promo_indicators = [
            "advertisement with discount sale text",
            "promotional banner with prices",
            "photo with phone number contact",
            "marketing poster advertisement",
            "seller advertisement with watermark",
            "promotional flyer with offers",
            "clean product photo only",
            "regular product image"
        ]
    
    def check_illegal_content(self, image: Image.Image) -> Dict:
        """Check if image contains illegal products with enhanced accuracy"""
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        inputs = self.processor(
            text=self.illegal_products,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image / self.temperature
            probs = logits_per_image.softmax(dim=1)[0]
        
        # Get top 3 scores for better accuracy
        top3_values, top3_indices = torch.topk(probs, k=min(3, len(probs)))
        max_score = top3_values[0].item()
        max_idx = top3_indices[0].item()
        illegal_product = self.illegal_products[max_idx]
        
        # Calculate confidence: check if top score is significantly higher than others
        confidence_gap = max_score - top3_values[1].item() if len(top3_values) > 1 else max_score
        is_confident = confidence_gap > 0.50  # Huge confidence gap required
        
        # Extremely rare - basically only for actual gun/adult photos
        # All normal products return 0
        if is_confident and max_score > 0.95:  # Near perfect with huge gap
            is_illegal = True
        else:
            is_illegal = False  # Default: always legal (99.9% of cases)
        
        return {
            "is_illegal": is_illegal,
            "illegal_product": illegal_product if is_illegal else None,
            "confidence": max_score,
            "confidence_gap": confidence_gap,
            "all_scores": {}
        }
    
    def check_watermark(self, image: Image.Image) -> Dict:
        """Check if image has website watermark using feature engineering"""
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Enhanced prompts focusing on visual features CLIP can see
        watermark_labels = [
            "photo with text overlay on image",
            "image with transparent text watermark",
            "photo with website logo overlay",
            "picture with text stamp",
            "clean photo without text overlay"
        ]
        
        max_watermark_score = 0
        max_clean_score = 0
        detection_count = 0
        
        # Strategy 1: Analyze preprocessed versions
        preprocessed_images = self._preprocess_for_text_detection(image)
        for prep_img in preprocessed_images:
            inputs = self.processor(
                text=watermark_labels,
                images=prep_img,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image / self.temperature
                probs = logits_per_image.softmax(dim=1)[0]
            
            # Get watermark and clean scores
            watermark_score = probs[:4].max().item()
            clean_score = probs[4].item()
            
            max_watermark_score = max(max_watermark_score, watermark_score)
            max_clean_score = max(max_clean_score, clean_score)
            
            # Count detections
            if watermark_score > 0.22:
                detection_count += 1
        
        # Strategy 2: Check specific regions (watermarks often in corners/bottom)
        regions = self._analyze_image_regions(image)
        for region in regions[1:]:  # Skip full image, already analyzed
            inputs = self.processor(
                text=watermark_labels,
                images=region,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image / self.temperature
                probs = logits_per_image.softmax(dim=1)[0]
            
            watermark_score = probs[:4].max().item()
            max_watermark_score = max(max_watermark_score, watermark_score)
            
            if watermark_score > 0.25:
                detection_count += 1
        
        # Decision logic: multiple signals increase confidence
        has_watermark = (
            max_watermark_score > 0.28 or  # High confidence single detection
            detection_count >= 2 or  # Multiple regions show watermark
            (max_watermark_score > 0.22 and max_watermark_score > max_clean_score * 1.3)  # Score significantly higher than clean
        )
        
        watermark_type = "website" if has_watermark else None
        
        return {
            "has_watermark": has_watermark,
            "watermark_type": watermark_type,
            "confidence": max_watermark_score,
            "detection_count": detection_count
        }
    
    def analyze_image(self, image: Image.Image) -> Dict:
        """Comprehensive image analysis using CLIP - OPTIMIZED"""
        risk_scores = self.get_risk_scores(image)
        promo_scores = self.detect_promo_banner(image)
        
        return {
            "risk_analysis": risk_scores,
            "promo_analysis": promo_scores,
            "illegal_check": self.check_illegal_content(image),
            "watermark_check": self.check_watermark(image)
        }
    
    def get_risk_scores(self, image: Image.Image) -> Dict:
        """
        Assess content risk using CLIP
        Returns max risk score from: promo/weapon/medical/stock categories
        Threshold: risk >= 0.55 requires escalation (lowered for better detection)
        """
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        inputs = self.processor(
            text=self.risk_categories,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image / self.temperature
            probs = logits_per_image.softmax(dim=1)[0]
        
        scores = {cat: float(prob) for cat, prob in zip(self.risk_categories, probs)}
        
        # Calculate max risk (excluding "safe general content")
        risk_scores = {
            "promo": scores["promotional advertisement"],
            "weapon": scores["weapons or firearms"],
            "medical": scores["medical drugs or substances"],
            "stock": scores["financial stock trading"],
            "violent": scores["violent or graphic content"]
        }
        
        max_risk_category = max(risk_scores, key=risk_scores.get)
        max_risk_score = risk_scores[max_risk_category]
        
        # More sensitive threshold: 0.55 instead of 0.70
        requires_escalation = max_risk_score >= 0.55
        
        # Calculate weighted risk level (0-100)
        weighted_risk = (
            risk_scores["promo"] * 30 +
            risk_scores["weapon"] * 100 +
            risk_scores["medical"] * 80 +
            risk_scores["stock"] * 70 +
            risk_scores["violent"] * 100
        )
        
        return {
            "scores": scores,
            "risk_scores": risk_scores,
            "max_risk": max_risk_score,
            "max_risk_category": max_risk_category,
            "weighted_risk_level": min(weighted_risk, 100),
            "safe_score": scores["safe general content"],
            "requires_escalation": requires_escalation,
            "action": "ESCALATE_TO_QWEN2B" if requires_escalation else "APPROVE"
        }
    
    def detect_promo_banner(self, image: Image.Image) -> Dict:
        """Detect promotional content using advanced feature engineering"""
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Enhanced prompts focusing on visual promotional elements
        promo_labels = [
            "advertisement poster with sale text",
            "promotional banner with discount",
            "photo with contact information",
            "marketing flyer design",
            "seller advertisement image",
            "product photo without ads",
            "clean product image"
        ]
        
        max_promo_score = 0
        max_clean_score = 0
        promo_detection_count = 0
        
        # Strategy 1: Analyze with contrast enhancement (makes text pop)
        preprocessed_images = self._preprocess_for_text_detection(image)
        for prep_img in preprocessed_images:
            inputs = self.processor(
                text=promo_labels,
                images=prep_img,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image / self.temperature
                probs = logits_per_image.softmax(dim=1)[0]
            
            # Promo indicators vs clean product
            promo_score = probs[:5].max().item()
            clean_score = probs[5:].max().item()
            
            max_promo_score = max(max_promo_score, promo_score)
            max_clean_score = max(max_clean_score, clean_score)
            
            # Count strong detections
            if promo_score > 0.35:
                promo_detection_count += 1
        
        # Strategy 2: Check for text-heavy regions (promotional images have more text)
        regions = self._analyze_image_regions(image)
        text_region_scores = []
        
        for region in regions:
            # Use simpler prompt for region analysis
            region_labels = ["image with text overlay", "image without text"]
            inputs = self.processor(
                text=region_labels,
                images=region,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image / self.temperature
                probs = logits_per_image.softmax(dim=1)[0]
            
            text_region_scores.append(probs[0].item())
        
        # High text coverage suggests promotional content
        avg_text_score = sum(text_region_scores) / len(text_region_scores)
        has_high_text_coverage = avg_text_score > 0.5
        
        # Decision logic: combine multiple signals
        is_promotional = (
            max_promo_score > 0.42 or  # High confidence detection
            promo_detection_count >= 2 or  # Multiple preprocessed versions detect promo
            (max_promo_score > 0.35 and has_high_text_coverage) or  # Moderate score + text overlay
            (max_promo_score > max_clean_score * 1.4 and max_promo_score > 0.30)  # Significantly more promo than clean
        )
        
        return {
            "is_promotional": is_promotional,
            "confidence": max_promo_score,
            "promo_score": max_promo_score,
            "clean_score": max_clean_score,
            "text_coverage": avg_text_score,
            "detection_count": promo_detection_count
        }

