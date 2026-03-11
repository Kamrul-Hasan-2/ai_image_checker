git clone https://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@github.com/Kamrul-Hasan-2/ai_image_checker.git

git clone https://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@github.com/Kamrul-Hasan-2/ai_chatbot.git



ssh jkz3myis93bkcr-64410c6d@ssh.runpod.io -i "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519"


ssh -p 13820 root@91.150.160.38 -L 8080:localhost:8080

ssh -i "C:\Users\BLG\Documents\ssh-key-ai\id_ed25519"  -p 30014 root@116.127.115.43 -L 8080:localhost:8080



ssh -p 25752 root@120.238.149.205 -L 8080:localhost:8080


Setup
pip install transformers

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install accelerate
pip install fastapi uvicorn
pip install opencv-python


kill -9 $(lsof -ti:8000) 2>/dev/null
nohup python3 main.py --port 8000 > server.log 2>&1 &

ngrok run -- ngrok http 5000


Window 1: python app_integrated.py (Server)
Window 2: ngrok http 5000 (Internet access)
Window 3: python mode_manager.py (Optional - manage modes)



my chatbot roadmap

step - 1st anyone send a msg then this msg go to groq api 
step - groq api find the intent ex : amake ekta 10k er modde laptop dekhan ,,, search api search like keyword - 10k tk laptop 
step - find the laptop and send me a msg like database 
step - database msg send the ai 
step - if dont understand the mood change ai to human always a api json show human or ai this 

this process are carefully please integrate 

kono kisu chay : 
sir amader apnar posonder kisu product ase and product gula holo 

sir apnar ei bisoy ti bapare amader arek jon protinidi apnar sathe jugajug korbe kisukhon somoy lagte pare 


kew jodi order korte chay 
	sir apni kon product ti order korte chacchen tar id othoba link ti din
	
	-- id / link intent 

http://128.199.144.145:5000/test