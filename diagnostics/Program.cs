using System;
using System.Drawing;
using System.IO;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyVersion("0.1.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("0.1.0.0")]

namespace SmartPDV.Diagnostics
{
    sealed class DiagnosticWindow : Form
    {
        readonly ComboBox location = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 160 };
        readonly ComboBox scenario = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 235 };
        readonly ComboBox observer = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 250 };
        readonly Button start = new Button { Text = "Preparar coleta", AutoSize = true };
        readonly Button stop = new Button { Text = "Parar", AutoSize = true, Enabled = false };
        readonly Button save = new Button { Text = "Salvar resumo", AutoSize = true, Enabled = false };
        readonly Button compare = new Button { Text = "Comparar resumos", AutoSize = true };
        readonly Button clear = new Button { Text = "Limpar", AutoSize = true };
        readonly Label status = new Label { AutoSize = true, ForeColor = Color.DarkBlue };
        readonly TextBox output = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Both, WordWrap = false, Dock = DockStyle.Fill, MaxLength = 100000 };
        readonly Timer timer = new Timer { Interval = 100 };
        NativeCapture capture;
        DateTime armedUntil;
        bool arming;
        string report;
        public DiagnosticWindow()
        {
            Text = "Smart Control — diagnóstico de entrada " + Summary.Version;
            Width = 1000; Height = 650; MinimumSize = new Size(700, 450); StartPosition = FormStartPosition.CenterScreen;
            location.Items.AddRange(new object[] { "Central", "PDV" }); location.SelectedIndex = 0;
            observer.Items.AddRange(new object[] { "Teclado — indicadores e tempo", "Raw Input — origem do dispositivo" }); observer.SelectedIndex = 0;
            scenario.Items.AddRange(new object[] { "Produto — leitor local", "Produto — leitura remota", "Cartão — leitor local", "Cartão — leitura remota", "Digitação de teste" }); scenario.SelectedIndex = 0;
            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4, Padding = new Padding(12) };
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize)); layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize)); layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            var explanation = new Label { AutoSize = true, MaximumSize = new Size(930, 0), Text = "Use sob supervisão, na mesma sessão Windows do aplicativo. Prepare, volte à tela desejada em 5 segundos e faça uma leitura. Escolha o observador e faça coletas separadas. Coleta passiva por até 30 segundos: somente categorias, contagens e faixas de tempo. Não digite senhas durante a coleta. Nenhum número de cartão é guardado; salvar o resumo é opcional. Esta ferramenta não modifica a VR nem envia comandos." };
            var controls = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, WrapContents = true };
            controls.Controls.AddRange(new Control[] { location, scenario, observer, start, stop, save, compare, clear });
            status.Text = "Inativo — nenhum observador de teclado instalado.";
            layout.Controls.Add(explanation, 0, 0); layout.Controls.Add(controls, 0, 1); layout.Controls.Add(status, 0, 2); layout.Controls.Add(output, 0, 3);
            Controls.Add(layout);
            start.Click += delegate { Arm(); };
            stop.Click += delegate { Finish(); };
            save.Click += delegate { Save(); };
            compare.Click += delegate { Compare(); };
            clear.Click += delegate { Finish(); report = null; output.Clear(); save.Enabled = false; };
            timer.Tick += delegate { TickCapture(); };
            FormClosing += delegate { timer.Stop(); if (capture != null) capture.Dispose(); report = null; };
        }
        void Arm()
        {
            report = null; output.Clear(); save.Enabled = false;
            start.Enabled = compare.Enabled = clear.Enabled = location.Enabled = scenario.Enabled = observer.Enabled = false;
            stop.Enabled = true; arming = true; armedUntil = DateTime.UtcNow.AddSeconds(5);
            status.Text = "Preparando — volte ao aplicativo em 5 segundos."; timer.Start();
        }
        void TickCapture()
        {
            if (arming)
            {
                if (DateTime.UtcNow < armedUntil) return;
                arming = false;
                bool raw = observer.SelectedIndex == 1;
                capture = new NativeCapture(new Summary(location.SelectedIndex == 0 ? "central" : "pdv", Summary.Scenarios[scenario.SelectedIndex], raw ? "raw_keyboard" : "keyboard_hook"), raw);
                try { capture.Start(Handle); }
                catch { capture.Dispose(); capture = null; Finish(); status.Text = "Falha ao iniciar os observadores. Nenhuma coleta válida; não conclua a causa a partir disso."; return; }
            }
            if (capture == null) return;
            capture.Tick();
            if (!capture.Active) { Finish(); return; }
            status.Text = "Coleta ativa — restam " + ((30000 - capture.Elapsed + 999) / 1000) + " segundos. Volte ao aplicativo e faça uma leitura.";
        }
        void Finish()
        {
            timer.Stop(); arming = false;
            if (capture != null)
            {
                capture.Stop("manual");
                report = Summary.Serializer().Serialize(capture.Report());
                bool failed = capture.ObservationFailed;
                capture.Dispose(); capture = null;
                output.Text = failed ? "Falha no observador; resumo descartado." : report; save.Enabled = !failed;
                if (failed) report = null;
            }
            start.Enabled = compare.Enabled = clear.Enabled = location.Enabled = scenario.Enabled = observer.Enabled = true;
            stop.Enabled = false;
            status.Text = "Inativo — observadores removidos. Resumo somente na memória até salvar ou limpar.";
        }
        protected override void WndProc(ref Message message)
        {
            if (message.Msg == 0xff && capture != null)
            {
                try { capture.RawInput(message.LParam); }
                catch { Finish(); status.Text = "Falha de observação. Coleta interrompida; não use este resumo para concluir a causa."; save.Enabled = false; report = null; }
            }
            // DefWindowProc still processes WM_INPUT cleanup; never consume keyboard events.
            base.WndProc(ref message);
        }
        void Save()
        {
            if (report == null) return;
            var metadata = Summary.Parse(report);
            using (var dialog = new SaveFileDialog { Filter = "Resumo sem dígitos (*.json)|*.json", FileName = metadata["location"] + "-" + metadata["scenario"] + "-" + metadata["observer_mode"] + ".json", OverwritePrompt = true })
            {
                if (dialog.ShowDialog(this) != DialogResult.OK) return;
                try { Reports.SaveNew(dialog.FileName, report); status.Text = "Resumo agregado salvo com acesso restrito à conta Windows e ao SYSTEM."; }
                catch { MessageBox.Show(this, "Não foi possível salvar com segurança. Escolha um nome novo em uma pasta local NTFS da sua conta. Nenhum arquivo existente será substituído.", "Resumo não salvo", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
            }
        }
        void Compare()
        {
            using (var dialog = new OpenFileDialog { Filter = "Resumo sem dígitos (*.json)|*.json", Multiselect = true, Title = "Selecione exatamente dois resumos" })
            {
                if (dialog.ShowDialog(this) != DialogResult.OK || dialog.FileNames.Length != 2) return;
                try { string comparison = Summary.Compare(Reports.Read(dialog.FileNames[0]), Reports.Read(dialog.FileNames[1])); report = null; save.Enabled = false; output.Text = comparison; }
                catch { MessageBox.Show(this, "Escolha dois resumos válidos desta versão e do mesmo observador (Teclado ou Raw Input). O conteúdo não foi exibido.", "Comparação indisponível", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
            }
        }
    }
    static class Reports
    {
        public static string Read(string path)
        {
            using (var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (var buffer = new MemoryStream())
            {
                byte[] block = new byte[4096]; int read;
                while ((read = file.Read(block, 0, block.Length)) > 0)
                {
                    if (buffer.Length + read > 65536) throw new ArgumentException("Summary too large");
                    buffer.Write(block, 0, read);
                }
                return new UTF8Encoding(false, true).GetString(buffer.ToArray());
            }
        }
        public static void SaveNew(string path, string json)
        {
            Summary.Parse(json); // Only the strict aggregate schema can ever be exported.
            if (File.Exists(path)) throw new IOException("Choose a new report name");
            var acl = new FileSecurity(); acl.SetAccessRuleProtection(true, false);
            var owner = WindowsIdentity.GetCurrent().User;
            acl.SetOwner(owner);
            foreach (var sid in new[] { owner, new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null) })
                acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl, AccessControlType.Allow));
            string temporary = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(path)), ".smartpdv-" + Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                using (var file = new FileStream(temporary, FileMode.CreateNew, FileSystemRights.Write, FileShare.None, 4096, FileOptions.WriteThrough, acl))
                {
                    byte[] bytes = new UTF8Encoding(false).GetBytes(json);
                    file.Write(bytes, 0, bytes.Length); file.Flush(true);
                }
                File.Move(temporary, path); // Atomic rename, never overwrite another report.
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
    }
    static class Program
    {
        [STAThread] static void Main()
        {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new DiagnosticWindow());
        }
    }
}
