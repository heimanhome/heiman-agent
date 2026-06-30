/**
 * Skills同步脚本
 * 用于将skills目录同步到OpenClaw插件目录
 * 
 * 用法: node scripts/sync-skills.mjs [--dry-run]
 */

import { existsSync, mkdirSync, copyFileSync, readdirSync, statSync, rmSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT_DIR = join(__dirname, '..');
const SKILLS_DIR = join(ROOT_DIR, 'skills');
const DIST_DIR = join(ROOT_DIR, 'dist', 'skills');

const DRY_RUN = process.argv.includes('--dry-run');

/**
 * 递归复制目录
 */
function copyDir(src, dest) {
  if (!existsSync(dest)) {
    mkdirSync(dest, { recursive: true });
  }
  
  const entries = readdirSync(src);
  
  for (const entry of entries) {
    const srcPath = join(src, entry);
    const destPath = join(dest, entry);
    const stat = statSync(srcPath);
    
    if (stat.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      if (DRY_RUN) {
        console.log(`  [DRY-RUN] Would copy: ${srcPath} -> ${destPath}`);
      } else {
        copyFileSync(srcPath, destPath);
        console.log(`  ✓ Copied: ${entry}`);
      }
    }
  }
}

/**
 * 删除目录
 */
function deleteDir(dir) {
  if (existsSync(dir)) {
    rmSync(dir, { recursive: true, force: true });
    console.log(`  ✓ Deleted: ${dir}`);
  }
}

/**
 * 主函数
 */
async function main() {
  console.log('🔄 Skills同步脚本\n');
  
  if (DRY_RUN) {
    console.log('⚠️  DRY-RUN 模式 - 不会实际复制文件\n');
  }
  
  // 1. 检查skills目录
  console.log('📁 检查Skills目录...');
  if (!existsSync(SKILLS_DIR)) {
    console.log('  ✗ Skills目录不存在');
    process.exit(1);
  }
  
  const skills = readdirSync(SKILLS_DIR).filter(name => {
    const stat = statSync(join(SKILLS_DIR, name));
    return stat.isDirectory();
  });
  
  console.log(`  ✓ 找到 ${skills.length} 个Skills:\n`);
  skills.forEach(name => console.log(`    - ${name}`));
  console.log();
  
  // 2. 确保dist目录存在
  console.log('📂 准备dist目录...');
  if (!existsSync(join(ROOT_DIR, 'dist'))) {
    if (DRY_RUN) {
      console.log('  [DRY-RUN] Would create: dist/');
    } else {
      mkdirSync(join(ROOT_DIR, 'dist'), { recursive: true });
      console.log('  ✓ Created: dist/');
    }
  }
  
  // 3. 清理旧的skills
  if (existsSync(DIST_DIR)) {
    console.log('\n🗑️  清理旧skills...');
    deleteDir(DIST_DIR);
  }
  
  // 4. 复制新的skills
  console.log('\n📤 同步skills到dist...');
  copyDir(SKILLS_DIR, DIST_DIR);
  
  // 5. 验证
  console.log('\n✅ 验证同步结果...');
  const distSkills = readdirSync(DIST_DIR);
  if (distSkills.length === skills.length) {
    console.log('  ✓ 同步完成，所有skills已复制\n');
  } else {
    console.log(`  ✗ 同步失败：期望 ${skills.length} 个，实际 ${distSkills.length} 个\n`);
    process.exit(1);
  }
  
  // 6. 统计
  let totalFiles = 0;
  function countFiles(dir) {
    const entries = readdirSync(dir);
    for (const entry of entries) {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) {
        countFiles(path);
      } else {
        totalFiles++;
      }
    }
  }
  countFiles(DIST_DIR);
  
  console.log('📊 统计信息:');
  console.log(`  - Skills数量: ${skills.length}`);
  console.log(`  - 文件总数: ${totalFiles}`);
  console.log(`  - 目标目录: ${DIST_DIR}\n`);
}

// 运行
main().catch(err => {
  console.error('\n❌ 同步失败:', err.message);
  process.exit(1);
});
