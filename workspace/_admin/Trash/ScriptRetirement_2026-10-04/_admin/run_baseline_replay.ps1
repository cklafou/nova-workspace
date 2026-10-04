Set-Location "C:\Users\lafou\Project_Nova\workspace"
python nova_body\nova_witness\replay.py --endpoint http://127.0.0.1:8080 --cases nova_body\nova_witness\golden_seed.jsonl *> logs\Temp\baseline_replay_2205.log
