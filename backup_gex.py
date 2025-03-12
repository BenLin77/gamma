import os
import shutil
from datetime import datetime, timedelta

def backup_old_files():
    # 源目錄和備份目錄
    source_dir = '/home/ben/pCloudDrive/stock/GEX/GEX_file'
    backup_base_dir = '/home/ben/pCloudDrive/stock/GEX/GEX_file_backup'
    
    # 獲取當前日期
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=5)
    
    # 遍歷源目錄（包括所有子目錄）
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            
            # 獲取檔案的修改時間
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # 如果檔案超過5天
            if file_mtime < cutoff_date:
                # 計算相對路徑，以保持目錄結構
                rel_path = os.path.relpath(root, source_dir)
                # 在備份目錄中創建對應的目錄結構
                backup_dir = os.path.join(backup_base_dir, rel_path)
                os.makedirs(backup_dir, exist_ok=True)
                
                # 目標檔案路徑
                backup_file_path = os.path.join(backup_dir, file)
                
                # 移動檔案
                try:
                    shutil.move(file_path, backup_file_path)
                    print(f"已移動: {file_path} -> {backup_file_path}")
                except Exception as e:
                    print(f"移動檔案時發生錯誤 {file_path}: {str(e)}")

if __name__ == "__main__":
    backup_old_files()
