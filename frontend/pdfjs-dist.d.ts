declare module "pdfjs-dist/build/pdf.mjs" {
  type PdfViewport = {
    width: number;
    height: number;
  };

  export const GlobalWorkerOptions: {
    workerSrc: string;
  };

  export function getDocument(src: string): {
    promise: Promise<{
      getPage(pageNumber: number): Promise<{
        getViewport(options: { scale: number }): PdfViewport;
        render(options: {
          canvasContext: CanvasRenderingContext2D;
          viewport: PdfViewport;
        }): {
          cancel?: () => void;
          promise: Promise<unknown>;
        };
      }>;
    }>;
  };
}
